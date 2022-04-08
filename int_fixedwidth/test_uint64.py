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
CAIRO_FILE_NAME = "uint64.cairo"
NAMESPACE = "Uint64"
BIT_LENGTH = 64
WORD_SIZE = 2**BIT_LENGTH  # MAX_VAL - MIN_VAL + 1
SHIFT = 2**BIT_LENGTH
MIN_VAL = 0
MAX_VAL = SHIFT - 1
ALL_ONES = WORD_SIZE - 1  # e.g. if BIT_LENGTH = 8 then ALL_ONES = 255
# The 128 in RC_BOUND below is fixed by the Cairo system
RC_BOUND = 2**128


# Imports

import os
from typing import List

import pytest
from cairotest import (
    AbstractCairoTestClass,
    CairoTest,
    SmartTest,
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
# Constructor for Uint datatype
Uint = getattr(smart_test.struct_factory.structs, NAMESPACE).Uint

# If the constant here don't match up with the corresponding constants in the Cairo source, then something might be not right
assert smart_test.test_object.program.get_const("BIT_LENGTH") == BIT_LENGTH
assert smart_test.test_object.program.get_const("SHIFT") == SHIFT


# first argument is a felt (i.e. an integer a such that 0 <= a < DEFAULT_PRIME, e.g. obtained from call to cairo function),
# second argument is any integer (e.g. arbitrary return of some Python computation returning an integer, which in particular may be negative),
# and they're equal modulo DEFAULT_PRIME
def assert_felt_eq_num(a, b):
    assert (0 <= a) and (a < DEFAULT_PRIME)
    assert a == b


# Datatypes

## "Some" inputs for unit tests.

some_num = [
    Uint(a)
    for a in [
        # some small numbers
        0,
        1,
        2,
        3,
        # good for testing pow2 and shl
        BIT_LENGTH - 1,
        BIT_LENGTH - 2,
        BIT_LENGTH,
        BIT_LENGTH + 1,
        # some big numbers
        MAX_VAL,
        MAX_VAL - 1,
        MAX_VAL - 2,
        # some half-way numbers (by division)
        SHIFT // 2,
        (SHIFT // 2) - 1,
        (SHIFT // 2) + 1,
        # some half-way numbers (by sqrt)
        2 ** (BIT_LENGTH // 2),
        (2 ** (BIT_LENGTH // 2)) - 1,
    ]
]
some_num_and_bool = [(a, b) for a in some_num for b in [0, 1]]  # linear length!
# some_num_and_felt is optimised to test shl and shr
some_num_and_felt = [
    (a, b)
    for a in some_num
    for b in [
        0,
        1,
        2,
        3,
        4,
        BIT_LENGTH // 2,
        BIT_LENGTH - 1,
        BIT_LENGTH,
        BIT_LENGTH + 1,
        BIT_LENGTH * 2,
    ]
]
some_num_pair = [(a, b) for a in some_num for b in some_num]  # quadratic length!


## "Arbitrary" inputs for property-based tests.

arbitrary_num = st.builds(Uint, st.integers(min_value=MIN_VAL, max_value=MAX_VAL))
arbitrary_bool = st.integers(
    min_value=0, max_value=1
)  # A bool in Cairo is just a felt that's 0 or 1

arbitrary_num_pair = st.tuples(arbitrary_num, arbitrary_num)
arbitrary_num_and_bool = st.tuples(arbitrary_num, arbitrary_bool)

arbitrary_felt = st.integers(min_value=0, max_value=DEFAULT_PRIME)
arbitrary_felt_pair = st.tuples(arbitrary_felt, arbitrary_felt)
arbitrary_num_and_felt = st.tuples(arbitrary_num, arbitrary_felt)


## "Some" and "Arbitrary" inputs designed for checking range-checks

some_num_possibly_out_of_bounds = some_num + [Uint(MAX_VAL + 1), Uint(MIN_VAL - 1)]
arbitrary_num_possibly_out_of_bounds = st.builds(
    Uint,
    st.integers(
        # // rounds negative numbers _down_, so add 1 to round up and then another 1
        -(2**70),  # -(DEFAULT_PRIME // 2) + 2,
        2**70,  # (DEFAULT_PRIME // 2) - 1,
    ),
)


# The tests themselves


####################### Tests on backend functions taking a pair of felts


class ExpectsFeltPair(AbstractCairoTestClass):
    argument_names = ["x", "y"]
    number_of_return_values = 1


@randomly_choose(arbitrary_felt_pair)
def test__bitwise_and(these_arguments):
    class ThisTest(ExpectsFeltPair):
        func_name = "bitwise_and"
        builtins = ["bitwise"]

        def success_function(a_in, b_in, res):
            expected_res = a_in & b_in
            assert res == expected_res

    smart_test.run(ThisTest, these_arguments)


@randomly_choose(arbitrary_felt_pair)
def test__bitwise_xor(these_arguments):
    class ThisTest(ExpectsFeltPair):
        func_name = "bitwise_xor"
        builtins = ["bitwise"]

        def success_function(a_in, b_in, res):
            expected_res = a_in ^ b_in
            assert res == expected_res

    smart_test.run(ThisTest, these_arguments)


@randomly_choose(arbitrary_felt_pair)
def test__is_le(these_arguments):
    class ThisTest(ExpectsFeltPair):
        func_name = "is_le"
        argument_names = ["a", "b"]
        builtins = ["range_check"]

        def success_function(a_in, b_in, res):
            expected_res = (
                1 if ((b_in - a_in) % DEFAULT_PRIME) < RC_BOUND else 0
            )  # condition from comment on is_le in cairo/common/math_cmp.cairo
            assert res == expected_res

    smart_test.run(ThisTest, these_arguments)


## Tests on a num not necessarily in bound (thus: which need not be in the interval [MIN_VAL, MAX_VAL])
# Set up test class


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


## Tests on functions taking a single uint

# Set up test class
class ExpectsSingleNum(AbstractCairoTestClass):
    argument_names = ["a"]
    number_of_return_values = 1


@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__not(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + ".not"
        builtins = []

        def success_function(a, res):
            assert_felt_eq_num(res, a.value ^ ALL_ONES)  # XOR with a bitmask

    smart_test.run(ThisTest, [these_arguments])


@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__neg(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + ".neg"
        builtins = []

        def success_function(a, res):
            assert_felt_eq_num(res, -a.value % SHIFT)
            # That number a' between 0 and MAX_VAL such that a' + a = 0 (mod SHIFT)

    smart_test.run(ThisTest, [these_arguments])


@unit_tests_on(some_num)
@randomly_choose(arbitrary_num)
def test__pow2(these_arguments):
    class ThisTest(ExpectsSingleNum):
        func_name = NAMESPACE + ".pow2"
        builtins = ["range_check"]

        # 2**a % 2**BIT_LENGTH
        def success_function(a, res):
            if a.value >= BIT_LENGTH:
                assert res == 0
            else:
                assert res == 2**a.value

    smart_test.run(ThisTest, [these_arguments])


## Tests on a uint pair

# Set up test class
class ExpectsNumPair(AbstractCairoTestClass):
    argument_names = ["a", "b"]


#### Factoring out some shared code
def eq_with_overflow(expected_num, res, overflow):
    assert res == (expected_num % SHIFT)
    assert overflow == expected_num // SHIFT


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__add(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".add"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a, b, res, carry):
            eq_with_overflow(a.value + b.value, res, carry)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__sub(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".sub"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a, b, res, borrow):
            # borrow is 1 if borrow occurrs, and
            # a_sub_b // SHIFT is -1 if borrow occurs
            eq_with_overflow(a.value - b.value, res, -borrow)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__mul(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".mul"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a, b, res, overflow):
            eq_with_overflow(a.value * b.value, res, overflow)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__div_rem(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".div_rem"
        number_of_return_values = 2
        builtins = ["range_check"]

        def success_function(a, b, res_quotient, res_remainder):
            if b.value == 0:  # divide by zero?
                assert res_quotient == 0
                assert res_remainder == 0
            else:
                expected_quotient, expected_remainder = divmod(
                    a.value, b.value
                )  # of course, divmod is in the cairo hint
                assert res_quotient == expected_quotient
                assert res_remainder == expected_remainder

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
            assert (res == 0) or (res == 1)
            assert (a.value == b.value) == (res == 1)

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__lt(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".lt"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a, b, res):
            assert (res == 1) == (a.value < b.value)  # if a < b then res should equal 1
            assert (res == 0) == (
                a.value >= b.value
            )  # if a >= b then res should equal 0

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_num_pair)
def test__le(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".le"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a, b, res):
            assert (res == 1) == (
                a.value <= b.value
            )  # if a.value <= b.value then res should equal 1
            assert (res == 0) == (a.value > b.value)  # if a > b then res should equal 0

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
            if b >= BIT_LENGTH:
                assert_felt_eq_num(res, 0)
            else:
                assert res == (a.value << b) % SHIFT

    smart_test.run(ThisTest, these_arguments)


@unit_tests_on(some_num_and_felt)
@randomly_choose(arbitrary_num_and_felt)
def test__shr(these_arguments):
    class ThisTest(ExpectsNumPair):
        func_name = NAMESPACE + ".shr__slow"
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a, b, res):
            assert_felt_eq_num(res, (a.value >> b) % SHIFT)

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
            if b == 1:
                assert res == -a.value % SHIFT
            elif b == 0:
                assert_felt_eq_num(res, a.value)
            else:
                raise ValueError(
                    "uint_cond_neg_test: invalid input.  Argument `b` should be 0 or 1 but you gave me ",
                    a.value,
                    b,
                )

        def failure_function(a, b):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, these_arguments)