# Welcome to the Cairo smart test framework (cairo-smart-test version 0.1.1)
#
# This provides tools for unit- and property-based testing Cairo code from within Python, including the following classes:
#
# * AbstractCairoFunctionClass stores data for calling a cairo function (e.g. the function's name and required builtins).
#
# * AbstractCairoTestClass extends AbstractCairoFunctionClass with success and failure functions for judging whether a call to a cairo function proceeded as expected.
#
# * CairoTest collects infrastructure for actually running tests on a particular Cairo test class (as above).  It's designed to interface well with PyTest and Hypothesis.
#
# * SmartTest wraps the CairoTest infrastructure with some extra state useful for diagnostics.  Most pertinently, if you use the SmartTest wrapper then you get improved access to run tests manually from the Python repl.
#
# To see an application of this framework, see the Cairo bitwise integer library.

import os
from pprint import pprint
from typing import List, Dict, Optional, Any

from hypothesis import example, note
from starkware.cairo.common.cairo_function_runner import CairoFunctionRunner
from starkware.cairo.lang.cairo_constants import DEFAULT_PRIME
from starkware.cairo.lang.compiler.cairo_compile import compile_cairo_files
from starkware.cairo.lang.compiler.program import Program


# A simple heuristic: if x is an integer half-way to being the maximal felt value, then represent it as a negative value
def felt_heuristic(x: Any):
    if isinstance(x, int):
        if x >= DEFAULT_PRIME // 2:
            return x - DEFAULT_PRIME
        else:
            return x
    elif isinstance(x, list) | isinstance(x, tuple):
        return list(map(felt_heuristic, x))
    else:
        return x


# An abstract class for invoking Cairo functions using CairoTest.invoke_function
class AbstractCairoFunctionClass:
    func_name: str  # name of cairo function to call
    argument_names: List[
        str
    ]  # ["<name of argument 1 to cairo function>", "<name of argument 2>", ...]
    number_of_return_values: int  # number of return values (measured in felts)
    builtins: List[str]  # ["<first required builtin>", ...]


# An abstract class for invoking tests using CairoTest.run_test_on.  This invokes the Cairo function and feeds the result into the success and failure functions.
class AbstractCairoTestClass(AbstractCairoFunctionClass):
    def success_function():  # input inputs and outputs
        raise NotImplementedError  # some code to run on inputs and outputs to decide if the test success is expected and "good"

    def failure_function():  # input inputs and outputs
        raise NotImplementedError  # some code to run on inputs to decide if the test failure is expected and "good"


## A class for invoking a Cairo function on some inputs, collecting its return values, and running a _test function_ on the input and result values to decide whether they are "good".
class CairoTest:
    def __init__(self, program):
        self.program = program

    # set up a Cairo runner object, invoke the Cairo function `func_name` on a dictionary of name-value pairs as inputs, with the named builtins, and return this runner state
    def invoke_function_by_name(
        self, func_name: str, inputs_dict: Dict[str, int], builtins: List[str]
    ):
        # set up a Cairo runner for our compiled program
        runner = CairoFunctionRunner(self.program)
        builtins_dict = {
            (builtin + "_ptr"): getattr(runner, builtin + "_builtin").base
            for builtin in builtins
        }  # getattr(runner,"method_name").base -> runner.method_name.base
        runner.run(func_name, **inputs_dict, **builtins_dict)
        return runner

    # `func_class` below should extend AbstractCairoFunctionClass.
    def invoke_function(
        self, func_class: AbstractCairoFunctionClass, argument_values: List[int]
    ):
        ## Call `func_class` on the inputs ...
        runner = self.invoke_function_by_name(
            func_class.func_name,
            dict(zip(func_class.argument_names, argument_values)),
            func_class.builtins,
        )
        # ... and collect the results.
        # (Can't guess the number of return values: user has to say.)
        results = runner.get_return_values(func_class.number_of_return_values)
        return results

    # `run` is the interface between the test case generators and the Cairo executable
    # It builds and executes a Cairo runner command on the inputs, collects the result(s), and invokes the test helper to evaluate whether the results are "good" wrt the inputs.
    # `test_class` below should extend AbstractCairoTestClass.
    def run(
        self,
        test_class: AbstractCairoTestClass,
        argument_values: List[int],
        results_accumulator: Optional[List[int]] = None,
    ):
        try:
            ## Invoke the `test_class` on the arguments provided ...
            results = self.invoke_function(test_class, argument_values)

        except:
            # Exception raised on function invocation?  
            # Test whether failure on inputs was expected and return
            try:
                test_class.failure_function(*argument_values)
                # If we end up here it means that:
                # * Invoking the function raised a runtime error
                # * test_class.failure_function expected a runtime error
                if results_accumulator != None:
                    results_accumulator.append(("Failure (as expected)", argument_values))
                # All is good, so return
                return
            except:
                # If we end up here it means that:
                # * Invoking the function raised a runtime error
                # * test_class.failure_function did not expect a runtime error.  Some debugging may be required!
                if results_accumulator != None:
                    results_accumulator.append(("!!!! Failure (NOT expected) !!!!", argument_values))
                # All is not good, so re-raise exception 
                raise 

        # No runtime error?  Test whether a successful run (inputs, outputs) is expected
        try:
            test_class.success_function(*argument_values, *results)
            # If we end up here it means that:
            # * Invoking the function completed successfully
            # * test_class.success_function expected this 
            if results_accumulator != None:
                results_accumulator.append(
                    ("Success (as expected)", argument_values, results)
                )
            # All is good, so return
            return
        except:
            # If we end up here it means that:
            # * Invoking the function completed successfully
            # * test_class.success_function expected a runtime error (so successful completion of the function is _not_ what we want or expect).  Some debugging may be required!
            if results_accumulator != None:
                results_accumulator.append(
                    ("!!!! Success (NOT expected) !!!!", argument_values, results)
                )
                # All is not good, so re-raise exception
                raise 


    ## A small utility to run a list of tests on a list of input argument values.  The test classes should all take argument values of the same types (e.g. "A pair of felts").
    def run_tests_with(
        self,
        list_of_test_classes: List[AbstractCairoTestClass],
        argument_values: List[int],
    ):
        for test_class in list_of_test_classes:
            note("Now running a test involving " + test_class.func_name + ":")
            self.run_test(test_class=test_class, argument_values=argument_values)


# simple wrapper for compile_cairo_files (useful below)
def compile_cairo_code_from_(filename: str):
    # Load the Cairo file ...
    CAIRO_FILE = os.path.join(os.path.dirname(__file__), filename)
    # ... and compile it
    return compile_cairo_files([CAIRO_FILE], prime=DEFAULT_PRIME)


# Smart diagnostic infrastructure
# Wraps a CairoTest test_object in smart test infrastructure, for convenient use both in hypothesis and in the repl


class SmartTest:
    # Initialise a smart test with either a filename (to be compiled using compile_cairo_code_from(filename)), or a precompiled test object, which in either case gets stored in self.test_object
    def __init__(self, test_object=None, filename=None):
        if (filename == None) & (test_object != None):
            # We have a test object?  Load it into self.test_object
            self.test_object = test_object
        elif (filename != None) & (test_object == None):
            # We have a file name?  Compile it and load it into self.test_object
            self.test_object = CairoTest(compile_cairo_code_from_(filename))
        else:
            raise ValueError(
                "Precisely one of filename and test_object should be provided here please."
            )

        # By default, run tests:
        self.run_tests = True
        # Initialising LastTest to None because there is no last test yet
        self.LastTest = None
        # Initialising results_accumulator to None.  Set it to [] to accumulate results
        self.results_accumulator = None

    # self.run saves the last test applied in self.LastTest, for convenient access during diagnostics.
    # If the flag self.run_tests is set to False, then self.run _only_ saves the test into self.LastTest -- it won't actually run it.
    # Set this flag to False if you just want to run a test to get access to it via self.LastTest, e.g. in the Python repl.
    # For example, if we assume we have a pytest file `test_int64.py` containing a test function `test__int_mul()` that runs a test on a smart test object `smart_test`, we might write (from within the Cairo virtual environment):
    #
    # python3 -i test_int64.py
    # smart_test.run_tests = False
    # test__int_mul()
    # int_mul_diagnostic = felt_heuristic(smart_test.invoke_LastTest_on([86,-5]))
    #
    # More usage examples are in the file `template_for_test_int.py`._

    def run(
        self, SomeCairoTestClass: AbstractCairoTestClass, some_arguments: List[int]
    ):
        if self.run_tests:  # run test switch set to True?
            self.test_object.run(
                SomeCairoTestClass, some_arguments, self.results_accumulator
            )
        self.LastTest = (
            SomeCairoTestClass  # stash the last test run, for later reference
        )

    # Run LastTest on some arguments.  Updates results_accumulator.
    def run_LastTest(self, some_arguments: List[int]):
        return self.run(self.LastTest, some_arguments)

    # Passthrough method directly to CairoTest.invoke_function.
    # Pulls the test_object from self.test_object, and the Cairo function to invoke from self.LastTest
    # _Just_ invokes the function and returns its results.
    # * Does not run tests on the results!
    # * Does not store results in results_accumulator!
    def invoke_LastTest_on(self, some_arguments: List[int]):
        return self.test_object.invoke_function(self.LastTest, some_arguments)

    # As the name suggests, if you're accumulating results then this will pretty-print them following a simple heuristic which works fairly well but may not be foolproof: feel free to adapt to your use case
    def pretty_print_accumulated_results(self):
        if self.results_accumulator == None:
            print(
                "To accumulate results, set your smart test object's `results_accumulator` variable to `[]` and run some tests -- `results_accumulator` will continue accumulating until you stop it or reset it."
            )
            print("To stop accumulating results, set `results_accumulator` to `None`.")
            print("To reset accumulating results, set `results_accumulator` to `[]`.")
        else:
            pprint(felt_heuristic(self.results_accumulator))


# A unit test builder.
# Technically, this is a decorator (higher-order function) which applies a function to a list of examples
def unit_tests_on(list_of_argument_values: List[List[int]]):
    def run_each_example_with_(f):
        for argument_values in list_of_argument_values:
            f = example(argument_values)(f)
        return f

    return run_each_example_with_
