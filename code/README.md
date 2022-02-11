## What is this directory?

The Cairo bitwise integer library, instantiated to various bit lengths.

For details including usage instructions, please see the top-level README file `README.md`.

```
cd ..
less README.md
```

## Run tests

To run this code's test suite type:

```
bash ./run_all_tests.sh
```

## Generate code

You can (re)generate the code in this directory by going up one level and executing `run-this-file-to-build-code-directory-from-template-directory.py`.

```
cd ..
python3 ./run-this-file-to-build-code-directory-from-template-directory.py
```

## Clean this directory

To clean this directory out (e.g. prior to regenerating the code), you can type:

```
rm int*.cairo uint*.cairo test_*.py run_all_tests.sh cairo_base_test_framework.py
rm -r __pycache__
```
from within this directory. **WARNING: `rm` erases data!**  Only type the command above if you know what you're doing.
