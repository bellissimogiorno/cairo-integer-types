# The _Cairo bitwise integer library_ (cairo-bitwise-int v0.2.0)
# The _Cairo smart test library_ (cairo-smart-test v0.2.0)

Author: Jamie Gabbay

## What is this?

The [Cairo Abstract Machine's](https://www.cairo-lang.org/) primitive notion of counting is a [finite field](https://en.wikipedia.org/wiki/Finite_field) over a prime of size approximately 2^251.  This differs significantly from that of a typical Intel or ARM chip, which is typically a 64-bit integer bitwise representation.

This directory contains:

* `cairo-bitwise-int`: a collection of Cairo libraries to _emulate_

    * signed and unsigned integer datatypes of various bit lengths (e.g. 8-bit unsigned integers, also known as 'bytes'), and
    * signed and unsigned unbounded integer datatypes.

* `cairo-smart-test`: an automated unit- and property-based test suite.

I am pleased to share this with the Cairo community, and feedback and suggestions are welcome.


## How to use the Cairo bitwise library off-the-shelf

The [`int_fixedwidth`](https://github.com/bellissimogiorno/cairo-integer-types/tree/main/int_fixedwidth) directory contains prepared source files.  For example:

* [`uint8.cairo`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/int_fixedwidth/uint8.cairo) is a library for unsigned 8-bit integers (i.e. "bytes").
* [`uint32.cairo`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/int_fixedwidth/uint32.cairo) is a library for unsigned 32-bit integers (i.e. "words").
* [`int32.cairo`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/int_fixedwidth/int32.cairo) is a library for signed 32-bit integers (i.e. "signed words").

Assuming you are writing Cairo code, You can import these libraries using [the usual Cairo library import mechanism](https://www.cairo-lang.org/docs/reference/syntax.html#library-imports).


## How to customise the library

### Templates and `BIT_LENGTH`

The fixedwidth integer code is templated over a `BIT_LENGTH` parameter which may vary between 4 and 125.

* The templates are in the [`templates`](https://github.com/bellissimogiorno/cairo-integer-types/tree/main/templates) directory.
* Generation of code from templates is controlled by the file `run-this-file-to-build-code-directory-from-template-directory.py`, which also contains a list of bit lengths to use.

This means that if you want an `int93.cairo` library, you can have one, by following the instructions below.

### The instructions

You'll need a working Cairo installation.  [Official Cairo install instructions are here](https://www.cairo-lang.org/docs/quickstart.html#installation) and [my own install script is below](#my-install) -- so do that first!  The rest of these instructions assume you're in a Cairo virtual environment.

We'll also assume you're using a Linux system; YMMV on other systems but the overall idea should be the same.

To set up:

* Make sure you have `jinja2` and (optionally for testing) `hypothesis` installed in your Cairo virtual environment, e.g. by typing `pip3 install jinja2 pytest hypothesis`.
* Execute the python3 file [`run-this-file-to-build-code-directory-from-template-directory.py`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/run-this-file-to-build-code-directory-from-template-directory.py) to build the [`int_fixedwidth`](https://github.com/bellissimogiorno/cairo-integer-types/tree/main/int_fixedwidth) directory using the templates in the [`templates`](https://github.com/bellissimogiorno/cairo-integer-types/tree/main/templates) directory.
* (Optionally) Execute the bash file [`run_all_tests.sh`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/int_fixedwidth/run_all_tests.sh) from inside the [`int_fixedwidth`](https://github.com/bellissimogiorno/cairo-integer-types/tree/main/int_fixedwidth) directory.

Let's say that again in code:

```
source ./enter-enviroment.sh
pip3 install jinja2 pytest hypothesis
python3 run-this-file-to-build-code-directory-from-template-directory.py
cd int_fixedwidth
bash run_all_tests.sh
```

For custom bit lengths, just edit the list of `bit_lengths` in [`run-this-file-to-build-code-directory-from-template-directory.py`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/run-this-file-to-build-code-directory-from-template-directory.py) ([direct link to line, correct at time of writing](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/run-this-file-to-build-code-directory-from-template-directory.py#L14)).

That's it!  The bitwise integer library files should now be in your `int_fixedwidth` directory and (optionally) fully tested.

### Unbounded integers

Unbounded signed and unsigned integers are also supported.  See the [`int_unbounded` directory](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/int_unbounded) directory.

## The Cairo smart test suite

The unit- and property-based test suite is in the file [`templates/cairo_smart_test_framework.py`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/templates/cairo_smart_test_framework.py).  The smart test suite is applied here to the bitwise library, but it exists independently and provides a comprehensive test framework for Cairo code.

You can use the smart test suite in your own Cairo development just by copying the [`templates/cairo_smart_test_framework.py`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/templates/cairo_smart_test_framework.py) file into your development and using it, following

* the documentation in that file, and
* the example usages in [`templates/template_for_test_int.py`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/templates/template_for_test_int.py), and
* a systematic demonstration of the test suite on a (deliberately buggy!) Cairo code file in the directory [`cairo-smart-test-demo`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/cairo-smart-test-demo).

Usage is designed to be straightforward but I'm happy to answer questions and act on feedback.

## Why do we need a Cairo bitwise integer library?

As you may know, Cairo's primitive numerical datatype is a _felt_ (field element) which is a number between 0 and [a constant DEFAULT_PRIME, currently set to just over 2^251](https://github.com/starkware-libs/cairo-lang/blob/64a7f6aed9757d3d8d6c28bd972df73272b0cb0a/src/starkware/cairo/lang/cairo_constants.py#L1).

However, the difference between the number model of Cairo and that of a typical computer chip goes deeper than the difference between 2^64 and 2^251.  For instance:

* In Cairo, every number element has a multiplicative inverse, since we are in a finite field. So for example "divide by two" is well-defined and is a bijection on the number space.  This is not the case for a typical bitwise representation!
* Conversely, Cairo has no native notions of "shift left one bit" or "shift right one bit" (multiplying or dividing by two is _not_ the same thing, in a finite field) -- nor of "add with overflow" (there _is_ no native notion of overflow, again because we are in a finite field), and so forth.

This sets up a representational mismatch between Cairo and bitwise-based models of computing on numbers.

The Cairo bitwise integer library helps to bridge this gap with suitable library emulations of "bitwise-flavoured" datatypes for numerical computations -- the ones you're probably used to, such as "64-bit unsigned integers" (see [`code/uint64.cairo`](https://github.com/bellissimogiorno/cairo-integer-types/blob/main/code/uint64.cairo)).

## Why do we need a Cairo test framework?

Seriously?  You do!  The code in this repo has been tested using a unit- and property-based test suite specifically designed to work well with Cairo.

## My install

This is what I type to get set up on a new machine.  Help yourself (but don't blame me if something goes wrong):

```
# Stuff we need to compile Python 3.7
sudo apt install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libsqlite3-dev libreadline-dev libffi-dev wget libbz2-dev
# Download Python 3.7 and cd into directory
wget https://www.python.org/ftp/python/3.7.13/Python-3.7.13.tgz
tar xvzf Python-3.7.13.tgz
cd Python-3.7.13
# Configure compilation
./configure --enable-optimizations
# Make (8 core system)
make -j 8
# Install
# IMPORTANT: altinstall means we don't overwrite your machine's native version of Python!
sudo make altinstall

# Create Python3.7 virtual environment
python3.7 -m venv ~/cairo_venv-3.7
# Jump into the venv
source ~/cairo_venv-3.7/bin/activate
# Install prerequisites to run cairo-bitwise-int and cairo-smart-test (works for Cairo 0.8)
pip3 install jinja2 pytest pytest-reverse hypothesis cairo-lang black pytest-xdist[psutil]

```

## Feedback and comments ...

... are very welcome.  Thanks in advance.
