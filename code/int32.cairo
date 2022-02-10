# Cairo library for arithmetic on signed 32-integers

from starkware.cairo.common.cairo_builtins import BitwiseBuiltin

# https://github.com/starkware-libs/cairo-lang/blob/master/src/starkware/cairo/common/math.cairo
from starkware.cairo.common.math import (
    assert_le, assert_nn_le, assert_not_zero, assert_in_range, assert_not_equal, assert_nn)
# https://github.com/starkware-libs/cairo-lang/blob/master/src/starkware/cairo/common/math_cmp.cairo
from starkware.cairo.common.math_cmp import is_nn, is_le, is_in_range
# https://github.com/starkware-libs/cairo-lang/blob/master/src/starkware/cairo/common/pow.cairo
from starkware.cairo.common.pow import pow
# https://github.com/starkware-libs/cairo-lang/blob/master/src/starkware/cairo/common/bitwise.cairo
from starkware.cairo.common.bitwise import bitwise_and, bitwise_or, bitwise_xor

# The file should be parametric over values for BIT_LENGTH up to 125
# To see where the limit of 125 comes from, see comments on `mul` in `template_for_uint.cairo` (not this file; the unsigned integer file).
const BIT_LENGTH = 32
const SHIFT = 2 ** 31

# Gather everything into a namespace for easier import
namespace Int32:

    # Represents a signed integer in the range [-SHIFT, SHIFT)
    # In other words, this is a numerical type with values in -SHIFT to SHIFT-1 inclusive.
    struct Int:
        member value : felt
    end


    # A trivial identity function, for diagnostic purposes
    func id(a : Int) -> (res : Int):
        return (res=a)
    end
 
    # Verifies that -SHIFT <= a < SHIFT .
    func num_check{range_check_ptr}(a : Int):
        assert_in_range(a.value, -SHIFT, SHIFT)
        return ()
    end

    # Calculate absolute value of a felt , and sign flag -1 (for strictly negative) and +1 (for nonnegative)
    # Designed to work for input -RANGE_CHECK_BOUND < a < RANGE_CHECK_BOUND.
    # Behaviour on input outside these bounds has not been considered.
    func felt_abs{range_check_ptr}(a : felt) -> (res : felt, sign : felt):
        alloc_locals
        let (raw_sign) = is_nn(a)  # is_nn returns 1 if 0 <= a < RANGE_CHECK_BOUND and 0 otherwise
        local sign = (-1) + 2 * raw_sign  # sign holds 1 if  0 <= a < RANGE_CHECK_BOUND and -1 otherwise
        return (res=a * sign, sign=sign)
    end



    # ARITHMETIC

    # Adds two int.
    # Returns the result as an int, plus a bit (1, 0, or -1+PRIME) indicating if overflow has occured and if so in which direction.
    func add{range_check_ptr}(a : Int, b : Int) -> (res : Int, overflow : felt):
        alloc_locals
        local res : Int
        local overflow : felt
        %{
            a_plus_b = (ids.a.value + ids.b.value) % PRIME 
            if (a_plus_b >= ids.SHIFT) & (a_plus_b < 2*ids.SHIFT):
               (ids.overflow, ids.res.value) = (1, (a_plus_b - 2 * ids.SHIFT) % PRIME)
            elif (a_plus_b < PRIME - ids.SHIFT) & (PRIME - 2 * ids.SHIFT <= a_plus_b): 
               (ids.overflow, ids.res.value) = (-1 % PRIME, (a_plus_b + 2 * ids.SHIFT) % PRIME)
            else:
               (ids.overflow, ids.res.value) = (0, a_plus_b)
        %}

        assert overflow * overflow * overflow = overflow  # overflow is -1, 0 or 1
        assert res.value = a.value + b.value - overflow * (2 * SHIFT)
        num_check(res)

        return (res, overflow)
    end

    # Subtraction.
    # Returns the result as an int, plus a bit (1, 0, or -1+PRIME) indicating if overflow has occured and if so in which direction.
    # Note: the "obvious" implementation via `neg` is wrong, due to a corner case that b = -SHIFT!  E.g. -1 - (-SHIFT) should be SHIFT-1, not -1-SHIFT.
    func sub{range_check_ptr}(a : Int, b : Int) -> (res : Int, overflow : felt):
        alloc_locals
        local res : Int
        local overflow : felt
        %{
            a_sub_b = (ids.a.value - ids.b.value) % PRIME 
            if (a_sub_b >= ids.SHIFT) & (a_sub_b < 2*ids.SHIFT):
               (ids.overflow, ids.res.value) = (1, (a_sub_b - 2 * ids.SHIFT) % PRIME)
            elif (a_sub_b < PRIME - ids.SHIFT) & (PRIME - 2 * ids.SHIFT <= a_sub_b): 
               (ids.overflow, ids.res.value) = (-1 % PRIME, (a_sub_b + 2 * ids.SHIFT) % PRIME)
            else:
               (ids.overflow, ids.res.value) = (0, a_sub_b)
        %}

        assert overflow * overflow * overflow = overflow  # overflow is -1, 0 or 1
        assert res.value = a.value - b.value - overflow * (2 * SHIFT)
        num_check(res)

        return (res, overflow)
    end


    # Multiplies two int.
    # Returns the result as two int (low and high parts).
    func mul{range_check_ptr}(a : Int, b : Int) -> (res : Int, overflow : Int):
        alloc_locals
        # let's guess values for m_overflow and m_res such that a * b = m_res + SHIFT * m_overflow
        local m_overflow : felt
        local m_res : felt
        # THE RUNNER
        %{
            # Let's figure out what a and b were as Python integers in [-SHIFT, SHIFT):
            a_value = ids.a.value if ids.a.value < ids.SHIFT else ids.a.value - PRIME
            b_value = ids.b.value if ids.b.value < ids.SHIFT else ids.b.value - PRIME
            # Multiply them 
            m_value = a_value * b_value
            # Do the division 
            (runner_overflow, runner_res) = divmod(m_value, 2 * ids.SHIFT)
            # runner_res is nearly what we want ... but it's in [0, 2 * SHIFT) whereas we need something in [-SHIFT, SHIFT).
            if runner_res >= ids.SHIFT:
               ids.m_res = (runner_res - 2 * ids.SHIFT) % PRIME 
               ids.m_overflow = (runner_overflow + 1) % PRIME
            else:
               ids.m_res = runner_res 
               ids.m_overflow = runner_overflow % PRIME
            # Worked example:
            # Suppose SHIFT = 128 (so 8-bit integers) and m_value = -127.
            # Then divmod(-127, 256) = (-1, 129) and m_res = -127 and m_overflow = 0
            # Then divmod(-129, 256) = (-1, 127) and m_res = 127 and m_overflow = -1
        %}
        # THE VALIDATOR:
        # We have nondeterministically chosen values for m_overflow and m_res.
        num_check(Int(m_res))
        num_check(Int(m_overflow))
        assert m_res + (m_overflow * (2 * SHIFT)) = a.value * b.value
        # Lucky guess!  Return these values:
        return (res=Int(m_res), overflow=Int(m_overflow))
    end

    # Division between int.
    # Returns the quotient and the remainder.
    # Conforms to EVM specifications: division by 0 yields 0.
    func div_rem{range_check_ptr}(a : Int, b : Int) -> (quotient : Int, remainder : Int):
        alloc_locals
        local quotient : Int
        local remainder : Int

        # If b == 0, return (0, 0).
        if b.value == 0:
            return (quotient=Int(0), remainder=Int(0))
        end
        # If b == -1, return (-a, 0).  (Note that -SHIFT / -1 = -SHIFT)
        if b.value == -1:
            let (quotient) = neg(a)  # this isn't just -a.value because -MIN_VAL = MIN_VAL
            return (quotient=quotient, remainder=Int(0))
        end

        # split a and b into a nonnegative absolute value, and a sign
        let (a_abs, a_sign) = felt_abs(a.value)
        let (b_abs, b_sign) = felt_abs(b.value)

        # python's divmod may behave differently from div_rem on negative inputs, but it's the same for nonnegative inputs
        %{ ids.quotient.value, ids.remainder.value = divmod(ids.a_abs, ids.b_abs) %}
        let (remainder_small) = lt(remainder, Int(b_abs))  # 0 <= remainder < b_abs
        assert remainder_small = 1
        let (quotient_small) = le(quotient, Int(a_abs))  # 0 <= quotient <= a
        assert quotient_small = 1
        let expected_value = b_abs * quotient.value + remainder.value
        assert expected_value = a_abs
        # So now we have |a|/|b| in quotient, and the signs of a and b in a_sign and b_sign.

        # The remainder should have the same sign as a: if a is positive then the remainder is positive; if a is negative then the remainder is negative
        let remainder_with_sign = Int(remainder.value * a_sign)

        # If a and b are both negative or both positive then the quotient should be positive.
        if a_sign == b_sign:
            return (quotient=quotient, remainder=remainder_with_sign)
        else:
            # If a and b have opposing signs (a is negative and b is positive, or vice versa) then the quotient should be negative
            let (quotient_neg) = neg(quotient)
            return (quotient=quotient_neg, remainder=remainder_with_sign)
        end
    end
    # Let's consider some examples of the above:
    # We expect div_rem(7, 2) = (3, 1), since 7 = 3*2+1
    # We expect div_rem(7, -2) = (-3, 1), since 7 = -3*-2 +1
    # We expect div_rem(-7, 2) = (-3, -1), since -7 = -3*2 -1
    # We expect div_rem(-7, -2) = (3, -1), since -7 = 3*-2 -1


    # 2**exp % 2**(BIT_LENGTH-2) as an int.
    # For example, if BIT_LENGTH = 8 then the maximum representable power of 2 is 2**6=64.
    func pow2{range_check_ptr}(a : Int) -> (res : Int):
        # If a < 0 or a > BIT_LENGTH - 2, then the result will be zero modulo 2**(BIT_LENGTH - 1).
        # is_in_range is inclusive on the left bound and exclusive on the right bound
        let (a_is_in_range) = is_in_range(a.value, 0, BIT_LENGTH - 1)
        if a_is_in_range == 0:
            return (Int(0))
        end
        let (res_value) = pow(2, a.value)
        return (Int(res_value))
    end


    # NEGATION AND BITWISE NOT

    # Returns the bitwise NOT of an integer.
    # E.g. for an 8-bit signed integer, not(127)=-128 and not(0)=-1.
    func not(a : Int) -> (res : Int):
        return (Int(-(a.value + 1)))
    end

    # Returns -x the negation of x, in the sense that it is that number such that x + -x = 0, if addition wraps around such that 127+1=-128 (examples given for 8-bit signed integers).
    # Note that -128 is -128, since -128+-128=0, and more generally neg(-SHIFT) = -SHIFT
    func neg(a : Int) -> (res : Int):
        if a.value == -SHIFT:
            return (res=a)
        else:
            return (res=Int(-a.value))
        end
    end

    # Conditionally negates an integer.
    # `b` below stands for `boolean`. It's a pun between "b the argument that follows a" and "b the boolean" (programmers can be very witty).
    # We intend `b` to have value 0 (don't negate) or 1 (do negate).
    func cond_neg(a : Int, b : felt) -> (res : Int):
        if b != 0:
            return neg(a)
        else:
            return (a)
        end
    end



    # COMPARISONS

    # Return true if integers are equal.
    func eq(a : Int, b : Int) -> (res):
        if a.value != b.value:
            return (0)
        else:
            return (1)
        end
    end

    # Returns 1 if the first integer is less than the second, otherwise returns 0.  Handles negative integers smoothly, because is_le does.
    func lt{range_check_ptr}(a : Int, b : Int) -> (res):
        return is_le(a.value + 1, b.value)
    end

    # Returns 1 if the first int is less than or equal to the second int, otherwise returns 0.
    func le{range_check_ptr}(a : Int, b : Int) -> (res):
        return is_le(a.value, b.value)
    end



    # BITWISE OPERATIONS (non-native on the Cairo abstract machine and therefore not as fast as you might expect of a bitwise architecture)


    # bitwise builtin in current Cairo version (cairo-lang==0.6.1) doesn't like numbers greater than or equal to 2^251.
    # Therefore, in the code below we adjust negative inputs upwards by adding an offset of (2 ** SHIFT).

    # bitwise XOR
    func xor{range_check_ptr, bitwise_ptr : BitwiseBuiltin*}(a : Int, b : Int) -> (res : Int):
        alloc_locals
        local res_value : felt
        let a_offset = a.value + SHIFT  # guarantee positive number, since minimum input value is DEFAULT_PRIME - SHIFT.  e.g. 0 maps to 128, 127 maps to 255, and -1 maps to 127.  This gets applied to _both_ inputs, so intuitively, XOR doesn't notice or care.
        let b_offset = b.value + SHIFT
        let (res_value) = bitwise_xor(a_offset, b_offset)
        let (must_shift) = is_le(SHIFT, res_value)  # If the result is SHIFT of greater, this indicates a twos complement negative value
        if must_shift == 1:
            return (Int(res_value - (2 * SHIFT)))
        else:
            return (Int(res_value))
        end
    end
    # Worked examples:
    # xor(0,-1)  ->   bitwise_xor(128,127) = 255   ->   -1
    # xor(0,-2)  ->   bitwise_xor(128,126) = 254   ->   -2
    # xor(127,-127)-> bitwise_xor(255,1)   = 254   ->   -2

    # # bitwise OR
    func or{range_check_ptr, bitwise_ptr : BitwiseBuiltin*}(a : Int, b : Int) -> (res : Int):
        alloc_locals
        local res_value : felt
        local a_offset : felt
        local b_offset : felt
        let (must_shift_a) = is_le(a.value, -1)  # are a or b negative?
        let (must_shift_b) = is_le(b.value, -1)
        if must_shift_a == 1:
            a_offset = a.value + (2 * SHIFT)
        else:
            a_offset = a.value
        end
        if must_shift_b == 1:
            b_offset = b.value + (2 * SHIFT)
        else:
            b_offset = b.value
        end
        let (res_value) = bitwise_or(a_offset, b_offset)
        let (must_shift) = is_le(SHIFT, res_value)
        if must_shift == 1:
            return (Int(res_value - (2 * SHIFT)))
        else:
            return (Int(res_value))
        end
    end

    # # bitwise AND
    func and{range_check_ptr, bitwise_ptr : BitwiseBuiltin*}(a : Int, b : Int) -> (res : Int):
        alloc_locals
        local res_value : felt
        local a_offset : felt
        local b_offset : felt
        let (must_shift_a) = is_le(a.value, -1)  # are a or b negative?
        let (must_shift_b) = is_le(b.value, -1)
        if must_shift_a == 1:
            a_offset = a.value + (2 * SHIFT)
        else:
            a_offset = a.value
        end
        if must_shift_b == 1:
            b_offset = b.value + (2 * SHIFT)
        else:
            b_offset = b.value
        end
        let (res_value) = bitwise_and(a_offset, b_offset)
        let (must_shift) = is_le(SHIFT, res_value)
        if must_shift == 1:
            return (Int(res_value - (2 * SHIFT)))
        else:
            return (Int(res_value))
        end
    end

    # Computes the logical left shift of an int.
    # Note: "fast" bitwise operations aren't available because in the Cairo abstract machine the primitive numerical datatype is a raw field element, not a raw bitstring
    func shl__slow{range_check_ptr}(a : Int, b : felt) -> (res : Int):
        let (b_is_in_range) = is_in_range(b, 0, BIT_LENGTH - 1)
        if b_is_in_range == 1:
            let (two_pow_b) = pow(2, b)
            let (res, _) = mul(a, Int(two_pow_b))
            return (res)
        end
        return (Int(0))
    end

    # Computes the logical right shift of an int.
    # Note: "fast" bitwise operations aren't available because in the Cairo abstract machine the primitive numerical datatype is a raw field element, not a raw bitstring
    func shr__slow{range_check_ptr}(a : Int, b : felt) -> (res : Int):
        alloc_locals
        if b == 0:
            return (a)
        end
        let (b_is_in_range) = is_in_range(b, 1, BIT_LENGTH - 1)
        # a_sign == -1 or +1
        let (a_abs, a_sign) = felt_abs(a.value)
        if b_is_in_range == 0:
            # -1 if a is negative, 0 if a is nonnegative
            return (Int((a_sign - 1) / 2))
        end
        let (two_pow_b) = pow(2, b)
        if a_sign == -1:
            let (res, _) = div_rem(Int(a_abs - 1), Int(two_pow_b))
            return (Int((-res.value) - 1))
        else:
            let (res, _) = div_rem(a, Int(two_pow_b))
            return (res)
        end
    end

end
# end namespace


# The code below should not be executed.  Its role is to reference the functions in the namespace above, to prevent the Cairo code optimiser from garbage-collecting the namespace's contents as dead code.
# One might call the code below a "dead code dead code eliminator eliminator", if one were inclined to dry wit.
func dead_code_dead_code_eliminator_eliminator_for_Int32_namespace{range_check_ptr, bitwise_ptr : BitwiseBuiltin*}():
   alloc_locals
   local a : felt
   local b : felt
   let num_a = Int32.Int(a)
   let num_b = Int32.Int(b)
   Int32.num_check{range_check_ptr=range_check_ptr}(num_a)
   Int32.felt_abs{range_check_ptr=range_check_ptr}(a)
   Int32.id(num_a)
   Int32.add{range_check_ptr=range_check_ptr}(num_a, num_b)
   Int32.sub{range_check_ptr=range_check_ptr}(num_a, num_b)
   Int32.mul{range_check_ptr=range_check_ptr}(num_a, num_b)
   Int32.div_rem{range_check_ptr=range_check_ptr}(num_a, num_b)
   Int32.pow2{range_check_ptr=range_check_ptr}(num_a)
   Int32.not(num_a)
   Int32.neg(num_a)
   Int32.cond_neg(num_a, b)
   Int32.eq(num_a, num_b)
   Int32.lt{range_check_ptr=range_check_ptr}(num_a, num_b)
   Int32.le{range_check_ptr=range_check_ptr}(num_a, num_b)
   Int32.xor{range_check_ptr=range_check_ptr, bitwise_ptr=bitwise_ptr}(num_a, num_b)
   Int32.or{range_check_ptr=range_check_ptr, bitwise_ptr=bitwise_ptr}(num_a, num_b)
   Int32.and{range_check_ptr=range_check_ptr, bitwise_ptr=bitwise_ptr}(num_a, num_b)
   Int32.shl__slow{range_check_ptr=range_check_ptr}(num_a, b)
   Int32.shr__slow{range_check_ptr=range_check_ptr}(num_a, b)
   return()
end
