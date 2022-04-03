#!/usr/bin/env python

from pathlib import Path
from shutil import copyfile

from jinja2 import Template

# Get templates from here (note trailing slash)
PATH_TO_TEMPLATES = "templates/"
# Write code to here
PATH_TO_CODE = "int_fixedwidth/"

# List of bit lengths for which we want to output code
bit_lengths = [4, 6, 8, 10, 12, 16, 32, 64, 124, 125]
# (bit lengths of 126 or more may be unsafe.  See comments on `uint_mul`.)

print()

# READING THE TEMPLATE FILES

# Helper function(s)

# Input a filename, read it in, and return it as a Jinja2 template
def read_template(filename: str):
    full_path = PATH_TO_TEMPLATES + filename
    print("Now reading template " + full_path)
    template = Path(full_path).read_text()
    return (Template(template), template)


# Now execute:

# Load up the template file as a Jinja2 template
print("Reading templates:\n")
(j2_uint_template, uint_template) = read_template("template_for_uint.cairo")
(j2_test_uint_template, test_uint_template) = read_template("template_for_test_uint.py")
(j2_int_template, int_template) = read_template("template_for_int.cairo")
(j2_test_int_template, test_int_template) = read_template("template_for_test_int.py")
print()

# WRITING THE CODE FILES

# Helper function(s)


def make_data(bit_length: int):
    data = {"BIT_LENGTH": str(bit_length), "BIT_LENGTH_MINUS_ONE": str(bit_length - 1)}
    return data


def instantiate_template_and_write_to_file(
    j2_template, filename_root: str, file_suffix: str, bit_length: int
):
    output_code_filename = (
        PATH_TO_CODE + filename_root + str(bit_length) + "." + file_suffix
    )
    data = make_data(bit_length)
    print(
        "Now writing template to file "
        + output_code_filename
        + " with value "
        + str(bit_length)
    )
    output_path = Path(output_code_filename)
    output_path.write_text(j2_template.render(data))


# Now execute:

print("Writing code files from templates:\n")
for bit_length in bit_lengths:
    instantiate_template_and_write_to_file(
        j2_template=j2_uint_template,
        filename_root="uint",
        file_suffix="cairo",
        bit_length=bit_length,
    )
    instantiate_template_and_write_to_file(
        j2_template=j2_test_uint_template,
        filename_root="test_uint",
        file_suffix="py",
        bit_length=bit_length,
    )
    instantiate_template_and_write_to_file(
        j2_template=j2_int_template,
        filename_root="int",
        file_suffix="cairo",
        bit_length=bit_length,
    )
    instantiate_template_and_write_to_file(
        j2_template=j2_test_int_template,
        filename_root="test_int",
        file_suffix="py",
        bit_length=bit_length,
    )
print()

print("Finally, copying over 'cairo_smart_test_framework.py' and 'run_all_tests.sh'.")
copyfile(
    PATH_TO_TEMPLATES + "cairo_smart_test_framework.py",
    PATH_TO_CODE + "cairo_smart_test_framework.py",
)
copyfile(PATH_TO_TEMPLATES + "run_all_tests.sh", PATH_TO_CODE + "run_all_tests.sh")

print()
print(
    "All done!  You should now have a full Cairo bitwise integer library in directory "
    + PATH_TO_CODE
)
print(
    "To test it, type 'bash run_all_tests.sh' from within that directory.  (It may take a while, so you could go make a cup of tea.)"
)
print()
