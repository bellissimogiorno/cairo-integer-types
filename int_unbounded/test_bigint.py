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

# TESTING (PYTEST AND HYPOTHESIS)
import pytest
from hypothesis import HealthCheck, event, example
from hypothesis import given as randomly_choose
from hypothesis import note, settings
from hypothesis import strategies as st

# IMPORT THE SMART TEST FRAMEWORK
from cairo_smart_test_framework import (
    AbstractCairoTestClass,
    CairoTest,
    SmartTest,
    chain,
    felt_heuristic,
    unit_tests_on,
    DEFAULT_PRIME,
)


# IMPORT SOME CONSTANTS
from biguint_tools import ALL_ONES  # SHIFT-1
from biguint_tools import MAX_VAL  # SHIFT-1
from biguint_tools import MIN_VAL  # 0
from biguint_tools import SHIFT  # 2 ** BIT_LENGTH
from biguint_tools import (
    BIT_LENGTH,
)  # File is parametric over BIT_LENGTH, which may range from 4 to 125.  Typically we would use 125, because it's more space-efficient. If you find that BIT_LENGTH is set to a smaller number, like 8, then this may have been for testing and somebody (= me) may have forgotten to set it back to 125.; Btw, why not use the full size of a felt (currently just a little larger than 2^251)?  Because we can multiply two 125-bit numbers and not overflow.
from biguint_tools import (
    EON,
)  # End-Of-Number marker.  Currently set to -1 (correct at time of writing).
from biguint_tools import (
    EON_MOD_PRIME,
)  # EON % DEFAULT_PRIME.  Following starkware.cairo.lang.cairo_constants.py, DEFAULT_PRIME = 2 ** 251 + 17 * 2 ** 192 + 1, so EON_MOD_PRIME = 2 ** 251 + 17 * 2 ** 192
from biguint_tools import (
    RC_BOUND,
)  # RC_BOUND is hard-wired to 2 ** 128 by the ambient Cairo system

# IMPORT SOME UTILITY FUNCTIONS
from biguint_tools import (
    add_eon,
    int_to_sign_and_abs,
    better_divmod,
    int_to_num,
    is_num,
    num_add,
    num_mul,
    num_sub,
    num_to_int,
    peek_one_num_from,
    some_num,
    strip_eon,
)


# Some key constants

CAIRO_FILE_NAME = "bigint.cairo"
NAMESPACE = "bigint."

# Load the Cairo file, compile it, and store this compiled code in a so-called `smart test object`.
smart_test = SmartTest(filename=CAIRO_FILE_NAME)


BigInt = smart_test.struct_factory.structs.bigint.BigInt


def mk_BigInt(a):
    return BigInt(*a)


def peek_one_bigint_from(memory, sign, ptr):
    return BigInt(
        felt_heuristic(sign),
        peek_one_num_from(memory=memory, pointer=ptr),
    )


# Check that the constants used here match up with the corresponding constants in the Cairo source.
# If not, then something might be not right!
assert smart_test.test_object.program.get_const("BIT_LENGTH") == BIT_LENGTH
assert smart_test.test_object.program.get_const("SHIFT") == SHIFT



def is_bigint(a):
    return (a.sign == -1 or a.sign == 1) and is_num(a.ptr)

def int_to_bigint(a):
    (a_sign, a_abs) = int_to_sign_and_abs(a)
    return BigInt(a_sign, int_to_num(a_abs))


def bigint_to_int(a):
    a_sign = a.sign
    a_abs = a.ptr
    return a_sign * num_to_int(a_abs)


# Datatypes

# A bool in Cairo is just a felt that's 0 or 1
arbitrary_bool = st.integers(min_value=0, max_value=1)
arbitrary_felt = st.integers(min_value=0, max_value=DEFAULT_PRIME)
arbitrary_felt_pair = st.tuples(arbitrary_felt, arbitrary_felt)


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
# arbitrary_biguint = st.builds(num_to_biguint, arbitrary_num)

arbitrary_uint_not_necessarily_in_range = st.integers(min_value=0, max_value=2 * SHIFT)
arbitrary_num_not_necessarily_in_range = st.builds(
    add_eon, st.lists(arbitrary_uint_not_necessarily_in_range)
)

# Various things can go wrong here:
# The sign might not be -1 or +1
# The absolute value might not be a num (it might have a digit out of range, or a trailing zero)
arbitrary_bigint_not_necessarily_in_range = st.builds(
    lambda a: BigInt(*a),
    st.tuples(
        st.sampled_from([-2, -1, 0, 1, 2]), arbitrary_num_not_necessarily_in_range
    ),
)

# BIGINT

# A sign (as used in the biguint Cairo code) is just a felt that's -1 or 1
arbitrary_sign = st.builds(lambda b: (b * 2) - 1, arbitrary_bool)

# A bigint is a pair of a sign and a biguint.  (0 has two representations, both of which are generated: (-1, 0) and (+1, 0).)
some_bigint = [BigInt(a_sign, a_abs) for a_sign in [-1, +1] for a_abs in some_num]
some_bigint_pair = [[a, b] for a in some_bigint for b in some_bigint]

arbitrary_bigint = st.builds(mk_BigInt, st.tuples(arbitrary_sign, arbitrary_num))
arbitrary_bigint_list = st.lists(arbitrary_bigint)
# 1/3 of the time, produce two bituints that are equal
arbitrary_bigint_pair = st.one_of(
    st.builds(lambda a: (a, a), arbitrary_bigint),
    st.tuples(arbitrary_bigint, arbitrary_bigint),
    st.tuples(arbitrary_bigint, arbitrary_bigint),
)

# We don't want to run multiplication test on inputs with too many digits, since biguint_mul is O(n^2).
def arbitrary_num_of_len_at_most(n):
    return st.builds(
        add_eon,
        arbitrary_uint_list.filter(
            lambda l: (l[-1] != 0 if len(l) > 0 else True) and len(l) <= n
        ),
    )


def arbitrary_bigint_of_len_at_most(n):
    return st.builds(
        mk_BigInt, st.tuples(arbitrary_sign, arbitrary_num_of_len_at_most(n))
    )


########################################
######## TESTS ON BIGINT UTILITY FUNCTIONS
########################################


@unit_tests_on(some_bigint)
@randomly_choose(arbitrary_bigint)
def test__bigint_lrl(a_bigint):
    if a_bigint == (-1, add_eon([])):
        assert int_to_bigint(bigint_to_int(a_bigint)) == (1, add_eon([]))
    else:
        assert int_to_bigint(bigint_to_int(a_bigint)) == a_bigint


@randomly_choose(arbitrary_unbounded_signed_int)  # this needs updated
def test__bigint_rlr(an_unbounded_signed_int):
    assert (
        bigint_to_int(int_to_bigint(an_unbounded_signed_int)) == an_unbounded_signed_int
    )


@randomly_choose(st.tuples(st.integers(), st.integers()))
def test__better_divmod(a_pair_of_integers):
    (a, b) = a_pair_of_integers
    (quotient, remainder) = better_divmod(a, b)
    if b == 0:
        assert quotient == 0 and remainder == 0
    else:
        assert a == quotient * b + remainder
        # if a is negative then the remainder should never be positive (i.e. "the sign of the remainder should be the sign of a")
        assert a >= 0 or remainder <= 0


########################################
######## TESTS ON SIGNED INTEGERS
########################################


# DATATYPE


@randomly_choose(arbitrary_bigint_not_necessarily_in_range)
def test__num_check(a_bigint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "num_check"
        builtins = ["range_check"]
        number_of_return_values = 0
        argument_names = ["a"]

        def success_function(a_in):
            assert is_bigint(a_in)

        def failure_function(a_in):
            assert not is_bigint(a_in)

    smart_test.run(ThisTest, [a_bigint])


@unit_tests_on(some_bigint)
@randomly_choose(arbitrary_bigint)
def test__id(a_bigint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "id"
        argument_names = ["a"]
        builtins = []
        number_of_return_values = None

        #            res = runner.get_return_values(1)
        #            return smart_test.struct_factory.structs.bigint.from_ptr(memory=runner.vm_memory, pointer=res)
        def get_return_values_function(runner, argument_values):
            (res_sign, res_ptr) = runner.get_return_values(2)
            return [peek_one_bigint_from(runner.vm_memory, res_sign, res_ptr)]

        def success_function(a_in, res):
            assert a_in == res

        def failure_function(a_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, (a_bigint,))


@unit_tests_on(some_bigint)
@randomly_choose(arbitrary_bigint)
def test__len(a_bigint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "len"
        argument_names = ["a"]
        builtins = []
        number_of_return_values = 1

        def success_function(a_in, res):
            assert len(a_in.ptr) == res + 1

        def failure_function(a_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, [a_bigint])


# EQUALITY


@unit_tests_on(some_bigint)
@randomly_choose(arbitrary_bigint)
def test__is_not_zero(a_bigint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "is_not_zero"
        argument_names = ["a"]
        builtins = []
        number_of_return_values = 1

        def success_function(a_in, res):
            # note that `or` evaluates left-to-right
            assert (
                (a_in == BigInt(sign=1, ptr=[EON]) and res == 0)
                or (a_in == BigInt(sign=-1, ptr=[EON]) and res == 0)
                or (res == 1)
            )

        def failure_function(a_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, [a_bigint])


@unit_tests_on(some_bigint_pair)
@randomly_choose(arbitrary_bigint_pair)
def test__is_eq(a_bigint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "is_eq"
        argument_names = ["a", "b"]
        builtins = []
        number_of_return_values = 1

        def success_function(a, b, res):
            # convert to int because 0 has two representations, as (-1, [EON]) and (+1, [EON])
            a_int = bigint_to_int(a)
            b_int = bigint_to_int(b)
            assert (a_int == b_int and res == 1) or (a_int != b_int and res == 0)

        def failure_function(a, b):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_bigint_pair)


@unit_tests_on(some_bigint_pair)
@randomly_choose(arbitrary_bigint_pair)
def test__assert_eq(a_bigint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "assert_eq"
        argument_names = ["a", "b"]
        builtins = []
        number_of_return_values = 0

        def success_function(a, b):
            assert bigint_to_int(a) == bigint_to_int(b)

        def failure_function(a, b):
            assert bigint_to_int(a) != bigint_to_int(b)

    smart_test.run(ThisTest, a_bigint_pair)


# COMPARISON


@unit_tests_on(some_bigint_pair)
@randomly_choose(arbitrary_bigint_pair)
def test__compare(a_bigint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "compare"
        argument_names = ["a", "b"]
        builtins = ["range_check"]
        number_of_return_values = 1

        def success_function(a_in, b_in, res):
            if bigint_to_int(a_in) < bigint_to_int(b_in):
                assert res == -1 % DEFAULT_PRIME
            elif bigint_to_int(a_in) == bigint_to_int(b_in):
                assert res == 0
            elif bigint_to_int(a_in) > bigint_to_int(b_in):
                assert res == 1

        def failure_function(a_in, b_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_bigint_pair)


@unit_tests_on(some_bigint_pair)
@randomly_choose(arbitrary_bigint_pair)
def test__is_lt(a_bigint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "is_lt"
        argument_names = ["a", "b"]
        builtins = ["range_check"]
        number_of_return_values = 1

        def success_function(a_in, b_in, res):
            assert (bigint_to_int(a_in) < bigint_to_int(b_in) and res == 1) or (
                bigint_to_int(a_in) >= bigint_to_int(b_in) and res == 0
            )

        def failure_function(a_in, b_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_bigint_pair)


@unit_tests_on(some_bigint_pair)
@randomly_choose(arbitrary_bigint_pair)
def test__is_le(a_bigint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "is_le"
        argument_names = ["a", "b"]
        builtins = ["range_check"]
        number_of_return_values = 1

        def success_function(a_in, b_in, res):
            assert (bigint_to_int(a_in) <= bigint_to_int(b_in) and res == 1) or (
                bigint_to_int(a_in) > bigint_to_int(b_in) and res == 0
            )

        def failure_function(a_in):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_bigint_pair)


# ARITHMETIC


@unit_tests_on(some_bigint)
@randomly_choose(arbitrary_bigint)
def test__neg(a_bigint):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "neg"
        argument_names = [
            "a",
        ]
        builtins = []
        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (res_sign, res_ptr) = runner.get_return_values(2)
            return [peek_one_bigint_from(runner.vm_memory, res_sign, res_ptr)]

        def success_function(a, res):
            assert bigint_to_int(a) == -1 * bigint_to_int(res)

        def failure_function(a):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, [a_bigint])


@unit_tests_on(some_bigint_pair)
@randomly_choose(arbitrary_bigint_pair)
def test__add(a_bigint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "add"
        argument_names = [
            "a",
            "b",
        ]
        builtins = ["range_check"]
        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (res_sign, res_ptr) = runner.get_return_values(2)
            return [peek_one_bigint_from(runner.vm_memory, res_sign, res_ptr)]

        def success_function(a, b, res):
            assert bigint_to_int(a) + bigint_to_int(b) == bigint_to_int(res)

        def failure_function(a, b):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_bigint_pair)


@unit_tests_on(some_bigint_pair)
@randomly_choose(arbitrary_bigint_pair)
def test__sub(a_bigint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "sub"
        argument_names = [
            "a",
            "b",
        ]
        builtins = ["range_check"]
        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (res_sign, res_ptr) = runner.get_return_values(2)
            return [peek_one_bigint_from(runner.vm_memory, res_sign, res_ptr)]

        def success_function(a, b, res):
            assert bigint_to_int(a) - bigint_to_int(b) == bigint_to_int(res)

        def failure_function(a, b):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_bigint_pair)


@unit_tests_on(some_bigint_pair)
@randomly_choose(
    st.tuples(arbitrary_bigint_of_len_at_most(3), arbitrary_bigint_of_len_at_most(3))
)
def test__mul(a_bigint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "mul"
        argument_names = [
            "a",
            "b",
        ]
        builtins = ["range_check"]

        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (res_sign, res_ptr) = runner.get_return_values(2)
            return [peek_one_bigint_from(runner.vm_memory, res_sign, res_ptr)]

        def success_function(a, b, res):
            assert bigint_to_int(a) * bigint_to_int(b) == bigint_to_int(res)

        def failure_function(a_sign, a_abs, b_sign, b_abs):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_bigint_pair)


@unit_tests_on(some_bigint_pair)
@randomly_choose(
    st.tuples(arbitrary_bigint_of_len_at_most(3), arbitrary_bigint_of_len_at_most(3))
)
def test__div(a_bigint_pair):
    class ThisTest(AbstractCairoTestClass):
        func_name = NAMESPACE + "div"
        argument_names = [
            "a",
            "b",
        ]
        builtins = ["range_check"]

        number_of_return_values = None

        def get_return_values_function(runner, argument_values):
            (
                res_sign,
                res_ptr,
                remainder_sign,
                remainder_ptr,
            ) = runner.get_return_values(4)
            return [
                peek_one_bigint_from(runner.vm_memory, res_sign, res_ptr),
                peek_one_bigint_from(runner.vm_memory, remainder_sign, remainder_ptr),
            ]

        def success_function(a, b, res, remainder):
            assert better_divmod(bigint_to_int(a), bigint_to_int(b)) == (
                bigint_to_int(res),
                bigint_to_int(remainder),
            )

        def failure_function(a_sign, a_abs, b_sign, b_abs):
            assert False, "Cairo run unexpectedly failed"

    smart_test.run(ThisTest, a_bigint_pair)
