# To run this file as a demo, type:
#    python3 -i test__simple_cairo_function.py
#
# To run this file through pytest, type:
#    pytest -svrPA test__simple_cairo_function.py

# To install hypothesis type `pip3 install hypothesis` (on a linux system)


# Some key constants

CAIRO_FILE_NAME = "simple_cairo_function.cairo"

# Imports

import os

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

smart_test = SmartTest(filename=CAIRO_FILE_NAME)


# Datatypes

## "Some" inputs for unit tests.  Data is always a list of tuples (even if tuple is 1-ary)

# Some numbers
# We need `list` here not because `map` is lazy, but because the product of `map` is consumed on first evaluation.
some_num = list(
    map(
        lambda a: (a,),
        list(range(16))
        + [2 ** 5 - 3, 2 ** 5 - 2, 2 ** 5 - 1, 2 ** 5, 2 ** 5 + 1, 2 ** 5 + 2],
    )
)
some_num_pair = [(a, b) for (a,) in some_num for (b,) in some_num]  # quadratic length!

## "Arbitrary" inputs for property-based tests.
arbitrary_felt_generator = st.integers(min_value=0, max_value=DEFAULT_PRIME)
arbitrary_felt_pair = st.tuples(arbitrary_felt_generator, arbitrary_felt_generator)

# The test

@unit_tests_on(some_num_pair)
@randomly_choose(arbitrary_felt_pair)
def test__is_double(these_arguments):
    class ThisTest(AbstractCairoTestClass):
        func_name = "is_double_uint5"
        argument_names = ["a", "b"]
        number_of_return_values = 1
        builtins = ["range_check"]

        def success_function(a, b, res):
            assert (a < 2 ** 5) & (b < 2 ** 5)
            assert ((a == 2 * b) & (res == 1)) | ((a != 2 * b) & (res == 0))

        def failure_function(a, b):
            assert (a >= 2 ** 5) | (b >= 2 ** 5)

    smart_test.run(ThisTest, these_arguments)


# Demo for test code (requires user interaction) 

print()
input("Let's view some test results.  Press any key to continue.")
print(
"""
smart_test.run_tests = True 
smart_test.results_accumulator = [] 
test__is_double()
smart_test.pretty_print_accumulated_results() 
""")
smart_test.run_tests = True 
smart_test.results_accumulator = [] 
# The Cairo code is deliberately buggy so this will raise an exception.  In Hypothesis this is good, but here we just silently absorb the exception 
try:
    test__is_double()
except:
    pass
smart_test.pretty_print_accumulated_results() 

print()
input("Let's do a more targetted test.  Press any key to continue.")
print(
"""
smart_test.results_accumulator = []
smart_test.run_LastTest([32,32])
smart_test.pretty_print_accumulated_results() 
""")
smart_test.results_accumulator = []
# The Cairo code is deliberately buggy so this will raise an exception.  We're expecting this so silently absorb the exception 
try:
   smart_test.run_LastTest([32,32])
except:
    pass
smart_test.pretty_print_accumulated_results() 

print()
input("Finally, let's invoke a function directly and examine the result.  Press any key to continue.")
print(
"""
print(smart_test.invoke_LastTest_on([32,32]))
""")
print(smart_test.invoke_LastTest_on([32,32]))

print()
print("Perfect!  We've homed in on an error case and can now debug our (deliberately buggy) Cairo code.")

print()
print("If you invoked this code using `pytest -svrPA test__simple_cairo_function.py` then Hypothesis will now run the tests, detect the errors in the code, and return flow of control to you.")
print("If you invoked this code using `python3 -i test__simple_cairo_function.py` then the demo is finished and flow of control will return to you.")
input("Press any key to continue.")
