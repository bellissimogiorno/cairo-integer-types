# To run this file type
#    pytest -rPA [filename]
# For verbose output type
#    pytest -vrPA [filename]
# To furthermore stop on first error (timesaving during development), type
#    pytest -xvrPA [filename]
# To see test timings add option
#           --durations=0

# To install hypothesis type `pip3 install hypothesis` (on a linux system)
# To run tests in reverse order, `pip3 install pytest-reverse` and run `pytest` with `--reverse` flag.  E.g.
#    pytest -xvrPA --reverse [filename]


# Imports

import os
from itertools import takewhile
from typing import List

import pytest

# IMPORT SOME UTILITY FUNCTIONS
# IMPORT SOME CONSTANTS
from biguint_tools import ALL_ONES  # SHIFT-1
from biguint_tools import MAX_VAL  # SHIFT-1
from biguint_tools import MIN_VAL  # 0
from biguint_tools import SHIFT  # 2 ** BIT_LENGTH
from biguint_tools import (  # File is parametric over BIT_LENGTH, which may range from 4 to 125.  Typically we would use 125, because it's more space-efficient. If you find that BIT_LENGTH is set to a smaller number, like 8, then this may have been for testing and somebody (= me) may have forgotten to set it back to 125.; Btw, why not use the full size of a felt (currently just a little larger than 2^251)?  Because we can multiply two 125-bit numbers and not overflow.; End-Of-Number marker.  Currently set to -1 (correct at time of writing).; EON % DEFAULT_PRIME.  Following starkware.cairo.lang.cairo_constants.py, DEFAULT_PRIME = 2 ** 251 + 17 * 2 ** 192 + 1, so EON_MOD_PRIME = 2 ** 251 + 17 * 2 ** 192.; RC_BOUND is hard-wired to 2 ** 128 by the ambient Cairo system
    BIT_LENGTH,
    EON,
    EON_MOD_PRIME,
    RC_BOUND,
    add_eon,
    int_to_num,
    is_num,
    num_add,
    num_mul,
    num_sub,
    num_to_int,
    peek_one_num_from,
    some_num,
    strip_eon,
    DEFAULT_PRIME,
)

# IMPORT THE SMART TEST FRAMEWORK
# `chain` maps [f1, f2, ..., fn] to "do f1, then f2, ..., then fn".
from cairo_smart_test_framework import (
    AbstractCairoTestClass,
    CairoTest,
    SmartTest,
    chain,
    felt_heuristic,
    unit_tests_on,
)
from hypothesis import HealthCheck, event, example
from hypothesis import given as randomly_choose
from hypothesis import note, settings
from hypothesis import strategies as st


# Some key constants

CAIRO_FILE_NAME = "biguint.cairo"
NAMESPACE = "biguint."

# Load the Cairo file, compile it, and store this compiled code in a so-called `smart test object`.
smart_test = SmartTest(filename=CAIRO_FILE_NAME)
BigUint = smart_test.struct_factory.structs.biguint.BigUint

# Check that the constants used here match up with the corresponding constants in the Cairo source.
# If not, then something might be not right!
assert smart_test.test_object.program.get_const("BIT_LENGTH") == BIT_LENGTH
assert smart_test.test_object.program.get_const("SHIFT") == SHIFT


# The native notion of numerical value for the bigint representation `num`, is a list of integers.
# A `bigint` is a `num`, terminated with an EON value (-1 at time of writing), then wrapped in a struct.
# These two functions biject between the `num` and `biguint` representations
num_to_biguint = lambda a: BigUint(a)
biguint_to_num = lambda a: a.ptr


int_to_biguint = chain(int_to_num, num_to_biguint)
biguint_to_int = chain(biguint_to_num, num_to_int)
# biguint_to_num just strips the Cairo BigUint struct wrapper.
is_biguint = chain(biguint_to_num, is_num)


def peek_one_biguint_from(memory, pointer):
    return num_to_biguint(peek_one_num_from(memory=memory, pointer=pointer))


int_to_signed_abs = lambda a: (1, a) if a >= 0 else (-1, -a)


def int_to_bigint(a):
    (a_sign, a_abs) = int_to_signed_abs(a)
    return (a_sign, int_to_num(a_abs))


def bigint_to_int(a):
    (a_sign, a_abs) = a
    return a_sign * num_to_int(a_abs)


# Datatypes

# A bool in Cairo is just a felt that's 0 or 1
arbitrary_bool = st.integers(min_value=0, max_value=1)
arbitrary_felt = st.integers(min_value=0, max_value=DEFAULT_PRIME)
arbitrary_felt_pair = st.tuples(arbitrary_felt, arbitrary_felt)

#########
# biguint
#########

# In order to interface with Cairo, a numerical element `num` must have a terminating element EON added, and then must be wrapped in a BigUint struct wrapper.  `num_to_biguint` takes care of this:
some_biguint = [num_to_biguint(a) for a in some_num]
some_biguint_pair = [[a, b] for a in some_biguint for b in some_biguint]

## "Arbitrary" inputs for property-based tests.
## Data is always a list of tuples (even if tuple is 1-ary)


arbitrary_unbounded_unsigned_int = st.integers(min_value=0, max_value=None)
arbitrary_unbounded_signed_int = st.integers()
# arbitrary_pretty_large_int = st.integers(min_value=0, max_value=SHIFT ** BIT_LENGTH)
arbitrary_uint = st.integers(
    min_value=0, max_value=SHIFT - 1
)  # range is inclusive, whence the SHIFT-1
arbitrary_uint_list = st.lists(arbitrary_uint)
# The final element of a bigint mustn't be 0 (e.g. [1] is a valid bigint and [1,0] is not), so filter those out:
arbitrary_num = st.builds(
    add_eon, arbitrary_uint_list.filter(lambda l: l[-1] != 0 if len(l) > 0 else True)
)
arbitrary_biguint = st.builds(num_to_biguint, arbitrary_num)

arbitrary_uint_not_necessarily_in_range = st.integers(min_value=0, max_value=2 * SHIFT)
arbitrary_num_not_necessarily_in_range = st.builds(
    add_eon, st.lists(arbitrary_uint_not_necessarily_in_range)
)
# Two things can go wrong when building the main body of a biguint, and need to be tested for:
# * A number out of range, e.g. [SHIFT] (should be [0,1])
# * A trailing zero, e.g. [1, 0] (should be [1])
arbitrary_biguint_not_necessarily_in_range = st.builds(
    num_to_biguint, arbitrary_num_not_necessarily_in_range
)
# 1/3 of the time, produce two bituints that are equal
arbitrary_biguint_pair = st.one_of(
    st.builds(lambda a: (a, a), arbitrary_biguint),
    st.tuples(arbitrary_biguint, arbitrary_biguint),
    st.tuples(arbitrary_biguint, arbitrary_biguint),
)

# BIGINT

# A sign (as used in the biguint Cairo code) is just a felt that's -1 or 1
arbitrary_sign = st.builds(lambda b: (b * 2) - 1, arbitrary_bool)

# A bigint is a pair of a sign and a biguint.  (0 has two representations: (-1, 0) and (+1, 0).)
some_bigint = [(a_sign, a_abs) for a_sign in [-1, +1] for a_abs in some_num]
some_bigint_pair = [[a, b] for a in some_bigint for b in some_bigint]

arbitrary_bigint = st.tuples(arbitrary_sign, arbitrary_num)
arbitrary_bigint_list = st.lists(arbitrary_bigint)

# We don't want to run multiplication test on inputs with too many digits, since biguint_mul is O(n^2).
def arbitrary_biguint_of_len_at_most(n):
    return st.builds(
        chain(add_eon, num_to_biguint),
        arbitrary_uint_list.filter(
            lambda l: (l[-1] != 0 if len(l) > 0 else True) and len(l) <= n
        ),
    )


def arbitrary_bigint_of_len_at_most(n):
    return st.tuples(arbitrary_sign, arbitrary_biguint_of_len_at_most(n))


########################################
######## TESTS ON BIGUINT UTILITY FUNCTIONS
########################################


@unit_tests_on(some_biguint)
@randomly_choose(arbitrary_biguint)
def test__utility_lrl(a_biguint):
    assert int_to_biguint(biguint_to_int(a_biguint)) == a_biguint


@randomly_choose(arbitrary_unbounded_unsigned_int)
def test__utility_rlr(an_unbounded_unsigned_int):
    assert (
        biguint_to_int(int_to_biguint(an_unbounded_unsigned_int))
        == an_unbounded_unsigned_int
    )


# Hypothesis might not consistently build _really_ large integers, so let's encourage a more uniform distribution
@unit_tests_on(some_biguint)
@randomly_choose(arbitrary_biguint)
def test__utility_rlr_again(a_biguint):
    some_pretty_large_int = biguint_to_int(
        a_biguint
    )  # this line depends on biguint_to_int working, at least to the extent of generating some large numbers
    a_cube = (
        some_pretty_large_int * some_pretty_large_int * some_pretty_large_int
    )  # this seems likely to be a _large_ number
    assert biguint_to_int(int_to_biguint(a_cube)) == a_cube


@unit_tests_on(some_biguint_pair)
@randomly_choose(arbitrary_biguint_pair)
def test__utility_sub(a_biguint_pair):
    (a, b) = a_biguint_pair
    (a_num, b_num) = map(biguint_to_num, (a, b))
    (sign, res_num) = num_sub(a_num, b_num)
    (a_int, b_int, res_int) = map(num_to_int, (a_num, b_num, res_num))
    if a_int >= b_int:
        assert (sign, res_int) == (1, a_int - b_int)
    else:
        assert (sign, res_int) == (-1, b_int - a_int)


########################################
######## TESTS ON UNSIGNED INTEGERS
########################################


@randomly_choose(arbitrary_biguint_not_necessarily_in_range)
def test__num_check(a_biguint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "num_check"
        builtins = ["range_check"]
        number_of_return_values = 0
        argument_names = ["a"]

        def success_function(a_in):
            assert is_biguint(a_in)

        def failure_function(a_in):
            # for diagnostics: print(felt_heuristic(a))
            assert not is_biguint(a_in)

    smart_test.run(ThisTest, [a_biguint])


# For diagnostics
# smart_test.diagnose_test(test__check)


@unit_tests_on(some_biguint)
@randomly_choose(arbitrary_biguint)
def test__id(a_biguint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "id"
        argument_names = ["a"]
        builtins = []
        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (res_pointer,) = runner.get_return_values(1)
            return [peek_one_biguint_from(memory=runner.vm_memory, pointer=res_pointer)]

        def success_function(a_in, res):
            # for diagnostics
            # print("Input: ", a_in)
            # print("Result: ", res)
            assert a_in == res

        def failure_function(a_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, [a_biguint])


# For diagnostics
# smart_test.diagnose_test(test__id)


@unit_tests_on(some_biguint)
@randomly_choose(arbitrary_biguint)
def test__len(a_biguint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "len"
        argument_names = ["a"]
        builtins = []
        number_of_return_values = 1

        def success_function(a_in, res):
            # for diagnostics
            # print("Input: ", a_in)
            # print("Result: ", res)
            # +1 because of the EON marker
            assert len(biguint_to_num(a_in)) == res + 1

        def failure_function(a_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, [a_biguint])


# For diagnostics
# smart_test.diagnose_test(test__id)


@randomly_choose(arbitrary_biguint)
def test__is_not_zero(a_biguint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "is_not_zero"
        argument_names = ["a"]
        builtins = []
        number_of_return_values = 1

        def success_function(a_in, res):
            # for diagnostics
            # print("Input: ", a_in)
            # print("Result: ", res)
            # Lets explicitly build what we expect the zero value to be, using lower-level functions:
            zero_value = num_to_biguint([EON])
            assert (a_in == zero_value and res == 0) or (
                a_in != zero_value and res == 1
            )

        def failure_function(a_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, [a_biguint])


# For diagnostics
# smart_test.diagnose_test(test__is_not_zero)


@randomly_choose(arbitrary_biguint_pair)
def test__is_eq(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "is_eq"
        argument_names = ["a", "b"]
        builtins = []
        number_of_return_values = 1

        def success_function(a_in, b_in, res):
            # for diagnostics
            # print("Input: ", a_in, b_in)
            # print("Result: ", res)
            assert (a_in == b_in and res == 1) or (a_in != b_in and res == 0)

        def failure_function(a_in, b_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_biguint_pair)


@randomly_choose(arbitrary_biguint_pair)
def test__assert_eq(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "assert_eq"
        argument_names = ["a", "b"]
        builtins = []
        number_of_return_values = 0

        def success_function(a_in, b_in):
            assert a_in == b_in

        def failure_function(a_in, b_in):
            assert a_in != b_in

    smart_test.run(ThisTest, a_biguint_pair)


# For diagnostics
# smart_test.diagnose_test(test__not_zero)


@unit_tests_on(some_biguint_pair)
@randomly_choose(arbitrary_biguint_pair)
def test__compare(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "compare"
        argument_names = ["a", "b"]
        builtins = ["range_check"]
        number_of_return_values = 1

        def success_function(a_in, b_in, res):
            if biguint_to_int(a_in) < biguint_to_int(b_in):
                assert res == -1 % DEFAULT_PRIME
            elif biguint_to_int(a_in) == biguint_to_int(b_in):
                assert res == 0
            elif biguint_to_int(a_in) > biguint_to_int(b_in):
                assert res == 1

        def failure_function(a_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_biguint_pair)


@unit_tests_on(some_biguint_pair)
@randomly_choose(arbitrary_biguint_pair)
def test__is_lt(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "is_lt"
        argument_names = ["a", "b"]
        builtins = ["range_check"]
        number_of_return_values = 1

        def success_function(a_in, b_in, res):
            assert (biguint_to_int(a_in) < biguint_to_int(b_in) and res == 1) or (
                biguint_to_int(a_in) >= biguint_to_int(b_in) and res == 0
            )

        def failure_function(a_in, b_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_biguint_pair)


@unit_tests_on(some_biguint_pair)
@randomly_choose(arbitrary_biguint_pair)
def test__is_le(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "is_le"
        argument_names = ["a", "b"]
        builtins = ["range_check"]
        number_of_return_values = 1

        def success_function(a_in, b_in, res):
            assert (biguint_to_int(a_in) <= biguint_to_int(b_in) and res == 1) or (
                biguint_to_int(a_in) > biguint_to_int(b_in) and res == 0
            )

        def failure_function(a_in, b_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_biguint_pair)


@unit_tests_on(some_biguint_pair)
@randomly_choose(arbitrary_biguint_pair)
def test__assert_sum_eq_with_carry(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "assert_sum_eq_with_carry"
        argument_names = [
            "a_digits_ptr",
            "b_digits_ptr",
            "res_digits_ptr",
            "last_carry",
        ]
        builtins = ["range_check"]
        number_of_return_values = 0

        def success_function(a, b, res, last_carry):
            assert num_to_int(a) + num_to_int(b) + last_carry == num_to_int(res)

        def failure_function(a, b, res, last_carry):
            assert False, "Cairo run unexpectedly failed"

    (a, b) = a_biguint_pair
    input_tuple = (a.ptr, b.ptr, num_add(a.ptr, b.ptr), 0)
    smart_test.run(ThisTest, input_tuple)


# For diagnostics
# smart_test.diagnose_test(test__assert_sum_eq_with_carry)
# Or this, if the above fails:
# smart_test.results_accumulator = []
# test__assert_sum_eq_with_carry()
# SmartTest.pretty_print_accumulated_results()


@unit_tests_on(some_biguint_pair)
@randomly_choose(arbitrary_biguint_pair)
def test__add(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "add"
        argument_names = [
            "a",
            "b",
        ]
        builtins = ["range_check"]

        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (res_pointer,) = runner.get_return_values(1)
            return [peek_one_biguint_from(memory=runner.vm_memory, pointer=res_pointer)]

        def success_function(a, b, res):
            assert biguint_to_int(a) + biguint_to_int(b) == biguint_to_int(res)

        def failure_function(a, b):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_biguint_pair)


@unit_tests_on(some_biguint_pair)
@randomly_choose(arbitrary_biguint_pair)
def test__sub(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "sub"
        argument_names = [
            "a",
            "b",
        ]
        builtins = ["range_check"]

        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (res_pointer, sign) = runner.get_return_values(2)
            return [
                peek_one_biguint_from(memory=runner.vm_memory, pointer=res_pointer),
                sign,
            ]

        def success_function(a, b, res, sign):
            if sign == 1:
                assert biguint_to_int(res) + biguint_to_int(b) == biguint_to_int(a)
            elif sign == (-1 % DEFAULT_PRIME):
                assert biguint_to_int(res) + biguint_to_int(a) == biguint_to_int(b)
            else:
                assert False, "Cairo run unexpectedly failed"

        def failure_function(a, b):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_biguint_pair)


@randomly_choose(
    st.tuples(arbitrary_biguint, st.integers(min_value=1, max_value=SHIFT - 1))
)
def test__mul_by_nonzero_digit_helper(a_biguint_and_uint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "mul_by_nonzero_digit_helper"
        argument_names = [
            "a_digits_ptr",
            "b",
            "res_digits_ptr",
            "last_carry",
        ]
        builtins = ["range_check"]

        number_of_return_values = 0

        def success_function(a, b, res, last_carry):
            assert num_to_int(a) * b + last_carry == num_to_int(res)

        def failure_function(a, b, res, last_carry):
            assert False, "Cairo run unexpectedly failed"

    (a, b) = a_biguint_and_uint
    input_tuple = (a.ptr, b, num_mul(a.ptr, int_to_num(b)), 0)
    smart_test.run(ThisTest, input_tuple)


@randomly_choose(
    st.tuples(arbitrary_biguint, st.integers(min_value=0, max_value=SHIFT - 1))
)
def test__mul_by_digit(a_biguint_and_a_digit):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "mul_by_digit"
        argument_names = [
            "a",
            "b",
        ]
        builtins = ["range_check"]

        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (res_pointer,) = runner.get_return_values(1)
            return [peek_one_biguint_from(memory=runner.vm_memory, pointer=res_pointer)]

        def success_function(a, b, res):
            assert biguint_to_int(a) * b == biguint_to_int(res)

        def failure_function(a, b):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_biguint_and_a_digit)


@unit_tests_on(some_biguint_pair)
@randomly_choose(
    st.tuples(arbitrary_biguint_of_len_at_most(3), arbitrary_biguint_of_len_at_most(3))
)
def test__mul(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "mul"
        argument_names = [
            "a",
            "b",
        ]
        builtins = ["range_check"]

        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (res_pointer,) = runner.get_return_values(1)
            return [peek_one_biguint_from(memory=runner.vm_memory, pointer=res_pointer)]

        def success_function(a, b, res):
            # for diagnostics
            # print("Input: ", a, b)
            # print("Result: ", res)
            assert biguint_to_int(a) * biguint_to_int(b) == biguint_to_int(res)

        def failure_function(a, b):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_biguint_pair)


@unit_tests_on(some_biguint_pair)
@randomly_choose(
    st.tuples(arbitrary_biguint_of_len_at_most(3), arbitrary_biguint_of_len_at_most(3))
)
def test__div(a_biguint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "div"
        argument_names = [
            "a",
            "b",
        ]
        builtins = ["range_check"]

        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (quotient_ptr, remainder_ptr) = runner.get_return_values(2)
            return [
                # smart_test.struct_factory.BigUint.from_ptr(memory=runner.vm_memory, addr=quotient_ptr),
                # smart_test.struct_factory.BigUint.from_ptr(memory=runner.vm_memory, addr=remainder_ptr),
                peek_one_biguint_from(memory=runner.vm_memory, pointer=quotient_ptr),
                peek_one_biguint_from(memory=runner.vm_memory, pointer=remainder_ptr),
            ]

        def success_function(a_in, b_in, quotient_out, remainder_out):
            (a, b) = (biguint_to_int(a_in), biguint_to_int(b_in))
            (quotient, remainder) = (
                biguint_to_int(quotient_out),
                biguint_to_int(remainder_out),
            )
            if a == 0 or b == 0:
                assert (quotient, remainder) == (0, 0)
            else:
                assert (quotient, remainder) == divmod(a, b)

        def failure_function(a, b):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_biguint_pair)


