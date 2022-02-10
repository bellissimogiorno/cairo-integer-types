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
CAIRO_FILE_NAME = "int6.cairo"
BIT_LENGTH = 6
WORD_SIZE = 2 ** BIT_LENGTH  # MAX_VAL - MIN_VAL + 1
SHIFT = 2 ** (BIT_LENGTH - 1)
MIN_VAL = -SHIFT
MAX_VAL = SHIFT - 1
ALL_ONES = WORD_SIZE - 1  # e.g. if BIT_LENGTH = 8 then ALL_ONES = 255
# The 128 in RC_BOUND below is fixed by the Cairo system
RC_BOUND = 2 ** 128

NAMESPACE = "Int6."

# Imports

import os
from typing import List

import pytest
from cairo_smart_test_framework import (
    AbstractCairoTestClass,
    CairoTest,
    SmartTest,
    felt_heuristic,
    unit_tests_on,
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

## Load the Cairo file, compile it, and store this compiled code in a so-called `smart test object`.
# CAIRO_FILE = os.path.join(os.path.dirname(__file__), CAIRO_FILE_NAME)
## Create a test object for the compiled Cario
# test_object = CairoTest(compile_cairo_files([CAIRO_FILE], prime=DEFAULT_PRIME))
## Wrap this in the smart test infrastructure for convenient use both in hypothesis and in the repl
# smart_test = SmartTest(test_object = test_object)
smart_test = SmartTest(filename=CAIRO_FILE_NAME)

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
    assert (0 <= a) & (a < DEFAULT_PRIME)
    assert mod_default_prime(a - b) == 0


# Datatypes

## "Some" inputs for unit tests.  Data is always a list of tuples (even if tuple is 1-ary)

# We need `list` here not because `map` is lazy, but because the product of `map` is consumed on first evaluation.
some_num = list(
    map(
        lambda a: (a,),
        [
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
        ],
    )
)
some_num_and_bool = [(a, b) for (a,) in some_num for b in [0, 1]]  # linear length!
some_num_pair = [(a, b) for (a,) in some_num for (b,) in some_num]  # quadratic length!
some_num_triple = [
    (a, b, c) for (a, b) in some_num_pair for (c,) in some_num
]  # cubic length! (not currently used)


## "Arbitrary" inputs for property-based tests.
## Data is always a list of tuples (even if tuple is 1-ary)

arbitrary_num_generator = st.integers(min_value=MIN_VAL, max_value=MAX_VAL)
arbitrary_bool_generator = st.integers(
    min_value=0, max_value=1
)  # A bool in Cairo is just a felt that's 0 or 1
arbitrary_num = st.tuples(
    arbitrary_num_generator,
)
arbitrary_num_pair = st.tuples(arbitrary_num_generator, arbitrary_num_generator)
arbitrary_num_and_bool = st.tuples(arbitrary_num_generator, arbitrary_bool_generator)

arbitrary_felt_generator = st.integers(min_value=0, max_value=DEFAULT_PRIME)
arbitrary_felt_pair = st.tuples(arbitrary_felt_generator, arbitrary_felt_generator)
arbitrary_num_and_felt = st.tuples(arbitrary_num_generator, arbitrary_felt_generator)


## "Some" and "Arbitrary" inputs designed for checking range-checks

some_num_possibly_out_of_bounds = some_num + [[MAX_VAL + 1], [MIN_VAL - 1]]
arbitrary_num_possibly_out_of_bounds = st.tuples(
    st.integers(
        (-RC_BOUND) + 1,  # inclusive left bound
        RC_BOUND,  # exclusive right bound
    )
)


# The tests themselves


### Tests on a num not necessarily in bound
#def test__bar():
#    class ThisTest(AbstractCairoTestClass):
#        argument_names = []
#        builtins = []
#        func_name = NAMESPACE + "bar"
#        number_of_return_values = 0
#
#        def success_function():
#            assert True 
#
#        def failure_function():
#            assert False 
#
#    smart_test.run(ThisTest, [])


# Set up test class


class ExpectsNumPossiblyOutOfBounds(AbstractCairoTestClass):
    argument_names = ["a"]
    builtins = ["range_check"]


@unit_tests_on(some_num_possibly_out_of_bounds)
@randomly_choose(arbitrary_num_possibly_out_of_bounds)
def test__num_check(these_arguments):
    class ThisTest(ExpectsNumPossiblyOutOfBounds):
        func_name = NAMESPACE + "num_check"
        number_of_return_values = 0

        def success_function(a_in):
            assert (MIN_VAL <= a_in) & (a_in <= MAX_VAL)

        def failure_function(a_in):
            assert (a_in < MIN_VAL) | (MAX_VAL < a_in)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_possibly_out_of_bounds)
@randomly_choose(arbitrary_num_possibly_out_of_bounds)
def test__felt_abs(these_arguments):
    class ThisTest(ExpectsNumPossiblyOutOfBounds):
        test_name = "felt_abs test"
        func_name = NAMESPACE + "felt_abs"
        number_of_return_values = 2

        # Works assuming -RC_BOUND < a_in < RC_BOUND
        def success_function(a_in, a_abs, a_sign):
            assert a_abs * felt_to_num(a_sign) == a_in

        def failure_function(a_in):
            assert False

    smart_test.run(ThisTest, these_arguments)


## Tests on functions taking a single num

# Set up test class
class ExpectsSingleNum(AbstractCairoTestClass):
    argument_names = ["a"]
    number_of_return_values = 1


# The Cairo abstract machine responds to negative inputs (at least if they are not too large -- I haven't tested the general case) by taking them modulo DEFAULT_PRIME


@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__id(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + "id"
        builtins = []

        def success_function(a_in, res):
            assert_felt_eq_num(res, a_in)

        # on some_num and arbitrary_num this is equivalent to:
        #       if a_in < 0:
        #            assert res == a_in + DEFAULT_PRIME
        #        else:
        #            assert res == a_in

    smart_test.run(ThisTest, these_arguments)


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
        func_name = NAMESPACE + "not"
        builtins = []

        def success_function(a_in, res):
            assert_felt_eq_num(res, -(a_in + 1))

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__neg(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + "neg"
        builtins = []

        def success_function(a_in, res):
            if a_in != MIN_VAL:
                assert_felt_eq_num(res, -a_in)
            else:
                assert_felt_eq_num(res, a_in)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__pow2(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + "pow2"
        builtins = ["range_check"]

        # 2**a % 2**(BIT_LENGTH-1)
        def success_function(a_in, res):
            if 0 <= a_in <= BIT_LENGTH - 2:
                assert res == 2 ** a_in
            else:
                assert res == 0

    smart_test.run(ThisTest, these_arguments)


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
        func_name = NAMESPACE + "add"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a_in, b_in, res, overflow):
            eq_with_overflow(a_in + b_in, res, overflow)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__sub(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + "sub"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a_in, b_in, res, overflow):
            eq_with_overflow(a_in - b_in, res, overflow)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__mul(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + "mul"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a_in, b_in, res, overflow):
            assert -SHIFT <= felt_to_num(overflow) < SHIFT
            assert -SHIFT <= felt_to_num(res) < SHIFT
            # We can't use assert_felt_eq_num because res + overflow * (2 * SHIFT) might not be in [0, DEFAULT_PRIME).  So we do it by hand:
            assert mod_default_prime(res + overflow * (2 * SHIFT) - a_in * b_in) == 0

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
        func_name = NAMESPACE + "div_rem"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a_in, b_in, quotient, remainder):
            # Massage the felt outputs (which are between 0 and DEFAULT_PRIME) to Python int values (between MIN_VAL and MAX_VAL)
            quotient_as_int = felt_to_num(quotient)
            remainder_as_int = felt_to_num(remainder)
            # let's get some corner cases out of the way first
            # divide by zero or divide zero?
            if (b_in == 0) | (a_in == 0):
                assert (quotient_as_int == 0) & (remainder_as_int == 0)
            # divide by -1 and not on the edge case of -2^BIT_LENGTH?
            elif (b_in == -1) & (a_in != MIN_VAL):
                assert (quotient_as_int == -a_in) & (remainder_as_int == 0)
            # divide by -1 and on that edge case of -2^BIT_LENGTH?
            elif (b_in == -1) & (a_in == MIN_VAL):
                assert (quotient_as_int == a_in) & (remainder_as_int == 0)
            else:
                # Phew -- it's not a corner case.  Time for some actual arithmetic.
                # Grab the signs of the inputs
                sign_of_a_in = 1 if 0 <= a_in else -1
                sign_of_b_in = 1 if 0 <= b_in else -1
                # Now check the result
                assert 0 <= (sign_of_a_in * remainder_as_int) < (sign_of_b_in * b_in)
                assert a_in == (b_in * quotient_as_int + remainder_as_int)
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
        func_name = NAMESPACE + "eq"
        number_of_return_values = 1
        builtins = []

        def success_function(a_in, b_in, res):
            assert (res == 0) | (res == 1)
            assert (a_in == b_in) == (res == 1)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__lt(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + "lt"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a_in, b_in, res):
            assert (res == 1) == (a_in < b_in)  # if a_in < b_in then res should equal 1
            assert (res == 0) == (
                a_in >= b_in
            )  # if a_in >= b_in then res should equal 0

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__le(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + "le"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a_in, b_in, res):
            assert (res == 1) == (
                a_in <= b_in
            )  # if a_in <= b_in then res should equal 1
            assert (res == 0) == (a_in > b_in)  # if a_in > b_in then res should equal 0

    smart_test.run(ThisTest, these_arguments)


### Bitwise


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__xor(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + "xor"
        number_of_return_values = 1
        builtins = ["range_check", "bitwise"]

        def success_function(a_in, b_in, res):
            assert_felt_eq_num(res, a_in ^ b_in)

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
        func_name = NAMESPACE + "and"
        number_of_return_values = 1
        builtins = ["range_check", "bitwise"]

        def success_function(a_in, b_in, res):
            assert_felt_eq_num(res, a_in & b_in)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__or(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + "or"
        number_of_return_values = 1
        builtins = ["range_check", "bitwise"]

        def success_function(a_in, b_in, res):
            assert_felt_eq_num(res, a_in | b_in)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__shl(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + "shl__slow"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a_in, b_in, res):
            assert b_in >= 0
            if b_in >= BIT_LENGTH - 1:
                assert_felt_eq_num(res, 0)
            else:
                unsigned_result = (a_in << b_in) & ALL_ONES
                if unsigned_result > MAX_VAL:
                    assert_felt_eq_num(res, unsigned_result - WORD_SIZE)
                else:
                    assert_felt_eq_num(res, unsigned_result)

        def failure_function(a_in, b_in):
            assert (b_in < 0) | (b_in >= RC_BOUND)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__shr(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + "shr__slow"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a_in, b_in, res):
            assert b_in >= 0
            if (b_in >= BIT_LENGTH - 1) & (a_in >= 0):
                assert_felt_eq_num(res, 0)
            elif (b_in >= BIT_LENGTH - 1) & (a_in < 0):
                assert_felt_eq_num(res, -1)
            else:
                expected_result = a_in >> b_in
                assert_felt_eq_num(res, expected_result)

        def failure_function(a_in, b_in):
            assert (b_in < 0) | (b_in >= RC_BOUND)

    smart_test.run(ThisTest, these_arguments)


## Tests of functions taking a pair of a num and a bool


@unit_tests_on(some_num_and_bool)
@randomly_choose(arbitrary_num_and_bool)
def test__cond_neg(these_arguments):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "cond_neg"
        argument_names = ["a", "b"]
        number_of_return_values = 1
        builtins = []

        def success_function(a_in, b_in, res):
            if (b_in == 1) & (a_in != MIN_VAL):
                assert_felt_eq_num(res, -a_in)
            elif (b_in == 1) & (a_in == MIN_VAL):
                assert_felt_eq_num(res, a_in)
            elif b_in == 0:
                assert_felt_eq_num(res, a_in)
            else:
                raise ValueError(
                    "uint_cond_neg_test: invalid input.  Argument `b_in` should be 0 or 1 but you gave me ",
                    a_in,
                    b_in,
                )

        def failure_function(a_in, b_in):
            assert False

    smart_test.run(ThisTest, these_arguments)


"""
smart_test.run_tests = False
test__cond_neg()
int_cond_neg_diagnostic = felt_heuristic([(i, smart_test.invoke_LastTest_on(i)) for i in some_num_and_bool])
"""