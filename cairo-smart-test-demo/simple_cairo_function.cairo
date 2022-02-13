# https://github.com/starkware-libs/cairo-lang/blob/master/src/starkware/cairo/common/math.cairo
from starkware.cairo.common.math import assert_le, assert_lt

# A simple but nontrivial example function to illustrate the Cairo smart test framework
# (so ... the function of this test function is to test our function testing functionality ...)

# The specification of is_double_uint32 is:
# If either a or b is greater than or equal to 2 ** 64, is_double(a,b) should fail.
# If a,b < 2^32 and b == 2*a then is_double(a,b) should return 1
# If a,b < 2^32 and b != 2*a then is_double(a,b) should return 0.

func is_double_uint5{range_check_ptr}(a : felt, b : felt) -> (res : felt):
    assert_le(a, 2 ** 5)
    assert_le(b, 2 ** 5)
    if a == 2 * b:
        return (1)
    else:
        return (0)
    end
end

# The code above may look fine at first glance, but it's wrong:
# 1. assert_le(a, 2**5) (less-than-or-equal) should read assert_lt (strictly less than)
# 2. assert_le(b, 2**5) (less-than-or-equal) should read assert_lt (strictly less than)
# The test in `test__simple_cairo_function.py` should detect this ...
