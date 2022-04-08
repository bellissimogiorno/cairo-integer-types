# To run this file type
#    pytest -rPA [filename]
# For verbose output type
#    pytest -vrPA [filename]
# To furthermore stop on first error (timesaving during development), type
#    pytest -xvrPA [filename]
# To see test timings add option
#           --durations=0

# To install hypothesis type `pip3 install hypothesis` (on a linux system)


# Some key constants

# File is parametric over values for BIT_LENGTH up to 128
CAIRO_FILE_NAME = "int16.cairo"
NAMESPACE = "Int16"
BIT_LENGTH = 16
WORD_SIZE = 2 ** BIT_LENGTH  # MAX_VAL - MIN_VAL + 1
SHIFT = 2 ** (BIT_LENGTH - 1)
MIN_VAL = -SHIFT
MAX_VAL = SHIFT - 1
ALL_ONES = WORD_SIZE - 1  # e.g. if BIT_LENGTH = 8 then ALL_ONES = 255
# The 128 in RC_BOUND below is fixed by the Cairo system
RC_BOUND = 2 ** 128


# Imports

import os
from typing import List

import pytest
from cairotest import (
    AbstractCairoTestClass,
    CairoTest,
    SmartTest,
    felt_heuristic,
    unit_tests_on,
    compile_cairo_files,
)
from hypothesis import HealthCheck, event
from hypothesis import given as randomly_choose
from hypothesis import note, settings
from hypothesis import strategies as st
from starkware.cairo.common.cairo_function_runner import CairoFunctionRunner
from starkware.cairo.lang.cairo_constants import DEFAULT_PRIME
from starkware.cairo.lang.compiler.cairo_compile import compile_cairo_files
from starkware.cairo.lang.compiler.program import Program
from starkware.starknet.public.abi import ADDR_BOUND, MAX_STORAGE_ITEM_SIZE


CAIRO_FILE = os.path.join(os.path.dirname(__file__), CAIRO_FILE_NAME)
COMPILED_CAIRO_FILE = compile_cairo_files([CAIRO_FILE], prime=DEFAULT_PRIME)
# Wrap the compiled code in a smart test object.
smart_test = SmartTest(compiled_file=COMPILED_CAIRO_FILE)
# Constructor for Int datatype
Int = getattr(smart_test.struct_factory.structs, NAMESPACE).Int

# If the constant here don't match up with the corresponding constants in the Cairo source, then something might be not right
assert smart_test.test_object.program.get_const("BIT_LENGTH") == BIT_LENGTH
assert smart_test.test_object.program.get_const("SHIFT") == SHIFT


## Some utility functions

# Rather crude function that treats a >= RC_BOUND as representing a negative integer.
# Works if 0 <= a < RC_BOUND or DEFAULT_PRIME-RC_BOUND < a < DEFAULT_PRIME
def felt_to_num(a):
    return a - DEFAULT_PRIME if a >= RC_BOUND else a


# modulo by DEFAULT_PRIME
def mod_default_prime(a):
    return a % DEFAULT_PRIME


# first argument is a felt (i.e. an integer a such that 0 <= a < DEFAULT_PRIME, e.g. obtained from call to cairo function),
# second argument is any integer (e.g. arbitrary return of some Python computation returning an integer, which in particular may be negative),
# and they're equal modulo DEFAULT_PRIME
def assert_felt_eq_num(a, b):
    assert (0 <= a) and (a < DEFAULT_PRIME)
    assert mod_default_prime(a - b) == 0


# Datatypes

## "Some" inputs for unit tests.

# Note: the Cairo abstract machine responds to negative inputs (at least if they are not too large -- I haven't tested the general case) by taking them modulo DEFAULT_PRIME
some_num = [Int(a) for a in [ 
            # some small numbers
            0,
            1,
            -1,
            2,
            -2,
            3,
            -3,
            # good for testing pow2 and shl
            BIT_LENGTH - 1,
            BIT_LENGTH - 2,
            BIT_LENGTH,
            BIT_LENGTH + 1,
            # some big numbers
            MAX_VAL,
            MAX_VAL - 1,
            MAX_VAL - 2,
            # some small numbers
            MIN_VAL,
            MIN_VAL + 1,
            MIN_VAL + 2,
            # some half-way numbers (by division)
            SHIFT // 2,
            (SHIFT // 2) - 1,
            (SHIFT // 2) + 1,
            # some half-way numbers (by sqrt)
            2 ** (BIT_LENGTH // 2),
            (2 ** (BIT_LENGTH // 2)) - 1,
        ]]
some_num_and_bool = [(a, b) for a in some_num for b in [0, 1]]  # linear length!
# some_num_and_felt is optimised to test shl and shr
some_num_and_felt = [(a, b) for a in some_num for b in [0, 1, 2, 3, 4, BIT_LENGTH // 2, BIT_LENGTH - 1, BIT_LENGTH, BIT_LENGTH + 1, BIT_LENGTH * 2]] 
some_num_pair = [(a, b) for a in some_num for b in some_num]  # quadratic length!


## "Arbitrary" inputs for property-based tests.
## Data is always a list of tuples (even if tuple is 1-ary)

arbitrary_num = st.builds(Int, st.integers(min_value=MIN_VAL, max_value=MAX_VAL))
arbitrary_bool = st.integers(
    min_value=0, max_value=1
)  # A bool in Cairo is just a felt that's 0 or 1

arbitrary_num_pair = st.tuples(arbitrary_num, arbitrary_num)
arbitrary_num_and_bool = st.tuples(arbitrary_num, arbitrary_bool)

arbitrary_felt = st.integers(min_value=0, max_value=DEFAULT_PRIME)
arbitrary_felt_pair = st.tuples(arbitrary_felt, arbitrary_felt)
arbitrary_num_and_felt = st.tuples(arbitrary_num, arbitrary_felt)


## "Some" and "Arbitrary" inputs designed for checking range-checks

some_num_possibly_out_of_bounds = some_num + [Int(MAX_VAL + 1), Int(MIN_VAL - 1)]
arbitrary_num_possibly_out_of_bounds = st.builds(Int, st.integers(
        (-RC_BOUND) + 1,  # inclusive left bound
        RC_BOUND,  # exclusive right bound
    )
)


# The tests themselves




####################### Tests on functions taking a single num not necessarily in bounds


class ExpectsNumPossiblyOutOfBounds(AbstractCairoTestClass):
    argument_names = ["a"]
    builtins = ["range_check"]


@unit_tests_on(some_num_possibly_out_of_bounds)
@randomly_choose(arbitrary_num_possibly_out_of_bounds)
def test__num_check(these_arguments):
    class ThisTest(ExpectsNumPossiblyOutOfBounds):
        func_name = NAMESPACE + ".num_check"
        number_of_return_values = 0

        def success_function(a):
            assert MIN_VAL <= a.value <= MAX_VAL

        def failure_function(a):
            assert a.value < MIN_VAL or MAX_VAL < a.value

    smart_test.run(ThisTest, [these_arguments])


@unit_tests_on(some_num_possibly_out_of_bounds)
@randomly_choose(arbitrary_num_possibly_out_of_bounds)
def test__felt_abs(these_arguments):
    class ThisTest(ExpectsNumPossiblyOutOfBounds):
        func_name = NAMESPACE + ".felt_abs"
        number_of_return_values = 2

        # Works assuming -RC_BOUND < a_in < RC_BOUND
        def success_function(a, a_abs, a_sign):
            assert a_abs * felt_to_num(a_sign) == a

        def failure_function(a):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, [these_arguments.value])


## Tests on functions taking a single num

# Set up test class
class ExpectsSingleNum(AbstractCairoTestClass):
    argument_names = ["a"]
    number_of_return_values = 1



@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__id(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + ".id"
        builtins = []

        # if a.value = -1 then we expect res = 1 + DEFAULT_PRIME 
        def success_function(a, res):
            assert_felt_eq_num(res, a.value)

    smart_test.run(ThisTest, [these_arguments])


"""
# Run this to view results: 
smart_test.run_tests = True 
smart_test.results_accumulator = [] 
test__id()
smart_test.pretty_print_accumulated_results() 
"""

"""
# Run this to hand-tailor specific diagnostics:
smart_test.run_tests = False
# Populate LastTest (without running any tests)
test__id()
# Populate a list of diagnostic results
int_id_diagnostic = [(i, smart_test.invoke_LastTest_on(i)) for i in some_num]
"""


@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__not(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + ".not"
        builtins = []

        def success_function(a, res):
            assert_felt_eq_num(res, -(a.value + 1))

    smart_test.run(ThisTest, [these_arguments])


@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__neg(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + ".neg"
        builtins = []

        def success_function(a, res):
            if a.value != MIN_VAL:
                assert_felt_eq_num(res, -a.value)
            else:
                assert_felt_eq_num(res, a.value)

    smart_test.run(ThisTest, [these_arguments])


@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__pow2(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + ".pow2"
        builtins = ["range_check"]

        # 2**a % 2**(BIT_LENGTH-1)
        def success_function(a, res):
            if 0 <= a.value <= BIT_LENGTH - 2:
                assert res == 2 ** a.value
            else:
                assert res == 0

    smart_test.run(ThisTest, [these_arguments])


## Tests on an int pair

# Set up test class
class ExpectsNumPair(AbstractCairoTestClass):
    argument_names = ["a", "b"]


#### Factoring out some shared code
def eq_with_overflow(expected_num, actual_felt_returned, overflow_bit):
    if expected_num > MAX_VAL:
        assert_felt_eq_num(actual_felt_returned, expected_num - WORD_SIZE)
        assert_felt_eq_num(overflow_bit, 1)
    elif expected_num < MIN_VAL:
        assert_felt_eq_num(actual_felt_returned, expected_num + WORD_SIZE)
        assert_felt_eq_num(overflow_bit, -1)
    else:
        assert_felt_eq_num(actual_felt_returned, expected_num)
        assert_felt_eq_num(overflow_bit, 0)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__add(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".add"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a, b, res, overflow):
            eq_with_overflow(a.value + b.value, res, overflow)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__sub(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".sub"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a, b, res, overflow):
            eq_with_overflow(a.value - b.value, res, overflow)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__mul(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".mul"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a, b, res, overflow):
            assert -SHIFT <= felt_to_num(overflow) < SHIFT
            assert -SHIFT <= felt_to_num(res) < SHIFT
            # We can't use assert_felt_eq_num because res + overflow * (2 * SHIFT) might not be in [0, DEFAULT_PRIME).  So we do it by hand:
            assert mod_default_prime(res + overflow * (2 * SHIFT) - a.value * b.value) == 0

    smart_test.run(ThisTest, these_arguments)


"""
# Run this to hand-tailor specific diagnostics:
smart_test.run_tests = False
# Populate LastTest (without running any tests)
test__mul()
# Populate a (short) list of diagnostic results
int_mul_diagnostic = felt_heuristic(smart_test.invoke_LastTest_on([86,-5]))
"""


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__div_rem(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".div_rem"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a, b, quotient, remainder):
            # Massage the felt outputs (which are between 0 and DEFAULT_PRIME) to Python int values (between MIN_VAL and MAX_VAL)
            quotient_as_int = felt_to_num(quotient)
            remainder_as_int = felt_to_num(remainder)
            # let's get some corner cases out of the way first
            # divide by zero or divide zero?
            if (b.value == 0) or (a.value == 0):
                assert (quotient_as_int == 0) and (remainder_as_int == 0)
            # divide by -1 and not on the edge case of -2^BIT_LENGTH?
            elif (b.value == -1) and (a.value != MIN_VAL):
                assert (quotient_as_int == -a.value) and (remainder_as_int == 0)
            # divide by -1 and on that edge case of -2^BIT_LENGTH?
            elif (b.value == -1) and (a.value == MIN_VAL):
                assert (quotient_as_int == a.value) and (remainder_as_int == 0)
            else:
                # Phew -- it's not a corner case.  Time for some actual arithmetic.
                # Grab the signs of the inputs
                sign_of_a_in = 1 if 0 <= a.value else -1
                sign_of_b_in = 1 if 0 <= b.value else -1
                # Now check the result
                assert 0 <= (sign_of_a_in * remainder_as_int) < (sign_of_b_in * b.value)
                assert a.value == (b.value * quotient_as_int + remainder_as_int)
            # This pair of asserts may seem slightly obscure: I derived it from these four examples
            # We expect int_div_rem(7, 2) = (3, 1), since 7 = 3*2+1
            # We expect int_div_rem(7, -2) = (-3, 1), since 7 = -3*-2 +1
            # We expect int_div_rem(-7, 2) = (-3, -1), since -7 = -3*2 -1
            # We expect int_div_rem(-7, -2) = (3, -1), since -7 = 3*-2 -1

    smart_test.run(ThisTest, these_arguments)


## Comparisons


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__eq(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".eq"
        number_of_return_values = 1
        builtins = []

        def success_function(a, b, res):
            assert (res == 1 and a.value == b.value) or (res == 0 and a.value != b.value)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__lt(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".lt"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a, b, res):
            assert (res == 1 and a.value < b.value) or (res == 0 and a.value >= b.value)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__le(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".le"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a, b, res):
            assert (res == 1 and a.value <= b.value) or (res == 0 and a.value > b.value)

    smart_test.run(ThisTest, these_arguments)


### Bitwise


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__xor(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".xor"
        number_of_return_values = 1
        builtins = ["range_check", "bitwise"]

        def success_function(a, b, res):
            assert_felt_eq_num(res, a.value ^ b.value)

    smart_test.run(ThisTest, these_arguments)


"""
# Run this to view results: 
smart_test.run_tests = True 
smart_test.results_accumulator = [] 
test__xor()
smart_test.pretty_print_accumulated_results() 
"""

"""
smart_test.run_tests = False
# Populate LastTest (without running any tests)
test__xor()
# Populate a (short) list of diagnostic results
int_xor_diagnostic = felt_heuristic([(i, smart_test.invoke_LastTest_on(i)) for i in some_num_pair])
"""


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__and(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".and"
        number_of_return_values = 1
        builtins = ["range_check", "bitwise"]

        def success_function(a, b, res):
            assert_felt_eq_num(res, a.value & b.value)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__or(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".or"
        number_of_return_values = 1
        builtins = ["range_check", "bitwise"]

        def success_function(a, b, res):
            assert_felt_eq_num(res, a.value | b.value)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_and_felt)
@randomly_choose(arbitrary_num_and_felt)
def test__shl(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".shl__slow"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a, b, res):
            assert b >= 0
            if b >= BIT_LENGTH - 1:
                assert_felt_eq_num(res, 0)
            else:
                unsigned_result = (a.value << b) & ALL_ONES
                if unsigned_result > MAX_VAL:
                    assert_felt_eq_num(res, unsigned_result - WORD_SIZE)
                else:
                    assert_felt_eq_num(res, unsigned_result)

        def failure_function(a, b):
            assert (b < 0) or (b >= RC_BOUND)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_and_felt)
@randomly_choose(arbitrary_num_and_felt)
def test__shr(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".shr__slow"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a, b, res):
            assert b >= 0
            if (b >= BIT_LENGTH - 1) and (a.value >= 0):
                assert_felt_eq_num(res, 0)
            elif (b >= BIT_LENGTH - 1) and (a.value < 0):
                assert_felt_eq_num(res, -1)
            else:
                expected_result = a.value >> b
                assert_felt_eq_num(res, expected_result)

        def failure_function(a, b):
            assert (b < 0) or (b >= RC_BOUND)

    smart_test.run(ThisTest, these_arguments)


## Tests of functions taking a pair of a num and a bool


@unit_tests_on(some_num_and_bool)
@randomly_choose(arbitrary_num_and_bool)
def test__cond_neg(these_arguments):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + ".cond_neg"
        argument_names = ["a", "b"]
        number_of_return_values = 1
        builtins = []

        def success_function(a, b, res):
            if (b == 1) and (a.value != MIN_VAL):
                assert_felt_eq_num(res, -a.value)
            elif (b == 1) and (a.value == MIN_VAL):
                assert_felt_eq_num(res, a.value)
            elif b == 0:
                assert_felt_eq_num(res, a.value)
            else:
                raise ValueError(
                    "uint_cond_neg_test: invalid input.  Argument `b` should be 0 or 1 but you gave me ",
                    a,
                    b,
                )

        def failure_function(a, b):
            assert False

    smart_test.run(ThisTest, these_arguments)


"""
smart_test.run_tests = False
test__cond_neg()
int_cond_neg_diagnostic = felt_heuristic([(i, smart_test.invoke_LastTest_on(i)) for i in some_num_and_bool])
"""