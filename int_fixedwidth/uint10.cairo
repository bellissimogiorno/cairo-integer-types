# Cairo library for arithmetic on unsigned 10-bit integers

from starkware.cairo.common.cairo_builtins import BitwiseBuiltin

# https://github.com/starkware-libs/cairo-lang/blob/master/src/starkware/cairo/common/math.cairo
from starkware.cairo.common.math import assert_le, assert_nn_le, assert_not_zero, assert_in_range
# https://github.com/starkware-libs/cairo-lang/blob/master/src/starkware/cairo/common/math_cmp.cairo
from starkware.cairo.common.math_cmp import is_le, is_in_range
# https://github.com/starkware-libs/cairo-lang/blob/master/src/starkware/cairo/common/pow.cairo
from starkware.cairo.common.pow import pow
# https://github.com/starkware-libs/cairo-lang/blob/master/src/starkware/cairo/common/bitwise.cairo
from starkware.cairo.common.bitwise import bitwise_and, bitwise_or, bitwise_xor

# Some constants
# The file should be parametric over values for BIT_LENGTH up to 125.
# To see where the limit of 125 comes from, see comments on `mul` (or search for 125).
const BIT_LENGTH = 10
const SHIFT = 2 ** 10


# Gather everything into a namespace for easier import
namespace Uint10:
    
    # Represents an unsigned integer in the range [0, SHIFT)
    # In other words, this is a numerical type with values in 0 to SHIFT-1 inclusive.
    struct Uint:
        member value : felt  
    end
    
    # Verifies that 0 <= a < SHIFT.
    func num_check{range_check_ptr}(a : Uint):
        assert_in_range(a.value, 0, SHIFT)
        return ()
    end
    
    # ARITHMETIC
    
    # Adds two uints, with carry bit.
    # Returns the result as a uint and a 1-bit carry bit
    func add{range_check_ptr}(a : Uint, b : Uint) -> (res : Uint, carry : felt):
        alloc_locals
        local res : Uint
        local carry : felt
        %{ (ids.carry, ids.res.value) = divmod(ids.a.value + ids.b.value, ids.SHIFT) %}
    
        assert carry * carry = carry  # carry is 0 or 1
        assert res.value = a.value + b.value - carry * SHIFT
        num_check(res)
    
        return (res, carry)
    end
    
    # Subtracts two integers.
    # Returns the result as a uint, plus a borrow bit indicating when wraparound has occurred.
    func sub{range_check_ptr}(a : Uint, b : Uint) -> (res : Uint, borrow : felt):
        alloc_locals
        local res : Uint
        local borrow : felt
        %{
            (carry, ids.res.value) = divmod(ids.a.value - ids.b.value, ids.SHIFT) 
            ids.borrow = -carry  # if b > a then carry is -1
        %}
    
        assert borrow * borrow = borrow  # borrow is 0 or 1
        assert res.value = a.value - b.value + borrow * SHIFT
        num_check(res)
    
        return (res, borrow)
    end
    
    # Multiplies two uint.
    # Returns the result as two uint (low and high parts).
    func mul{range_check_ptr}(a : Uint, b : Uint) -> (res : Uint, overflow : Uint):
        alloc_locals
        # let's guess values for m_overflow and m_res such that a * b = m_res + m_overflow * SHIFT
        local m_overflow : felt
        local m_res : felt
        # THE RUNNER
        %{
            # Calculate a * b
            m_value = ids.a.value * ids.b.value
            # Do the division 
            (ids.m_overflow, ids.m_res) = divmod(m_value, ids.SHIFT)
        %}
        # THE VALIDATOR: 
        num_check(Uint(m_res))
        num_check(Uint(m_overflow))
        # Validity of the check on the next line of cairo code depends on 
        # m_res + (m_overflow * SHIFT) > DEFAULT_PRIME being impossible.  
        # Thus we require (SHIFT - 1) + (SHIFT - 1) * SHIFT = (SHIFT - 1) * (SHIFT + 1) = SHIFT^2 - 1 < DEFAULT_PRIME. 
        # Since DEFAULT_PRIME is just above 2^251, it suffices to require SHIFT <= 2^125, thus BIT_LENGTH <= 125.
        assert m_res + (m_overflow * SHIFT) = a.value * b.value
        # Looks like it was a lucky guess!  Return these values:
        return (res=Uint(m_res), overflow=Uint(m_overflow))
    end
    
    # Division between uint.
    # Returns the quotient and the remainder.
    # Conforms to EVM specifications: division by 0 yields 0.
    func div_rem{range_check_ptr}(a : Uint, b : Uint) -> (
            quotient : Uint, remainder : Uint):
        alloc_locals
        local quotient : Uint
        local remainder : Uint
    
        # If b == 0, return (0, 0).
        if b.value == 0:
            return (quotient=Uint(0), remainder=Uint(0))
        end
    
        %{ ids.quotient.value, ids.remainder.value = divmod(ids.a.value, ids.b.value) %}
        let (res_mul, carry) = mul(quotient, b)  # res_mul = quotient * b
        assert carry = Uint(0)  # ... and no carry.
    
        let (check_val, add_overflow) = add(res_mul, remainder)  # check_val = res_mul+remainder, add_overflow is the overflow bit
        assert add_overflow = 0  # no overflow, and
        assert check_val = a  # a = check_val = res_mul + remainder
    
        let (is_valid) = lt(remainder, b)
        assert is_valid = 1
        return (quotient=quotient, remainder=remainder)  # this copies over quotient and remainder to ap-1 and ap-2
    end
    
    # 2**exp % 2**BIT_LENGTH as a uint
    func pow2{range_check_ptr}(a : Uint) -> (res : Uint):
        # If a >= BIT_LENGTH, the result will be zero modulo 2**BIT_LENGTH.
        let (overflow) = lt(a, Uint(BIT_LENGTH))
        if overflow == 0:
            return (Uint(0))
        end
        let (res) = pow(2, a.value)
        return (Uint(res))
    end
  
  
    # NEGATION AND BITWISE NOT
    
    # Returns the bitwise NOT of an integer.
    # E.g. for an 8-bit unsigned integer, not(255)=0 and not(128)=127.
    func not(a : Uint) -> (res : Uint):
        return (Uint((SHIFT - 1) - a.value))
    end
    
    # Returns -x the negation of x, in the sense that it is that number such that x + -x = 0, if addition wraps around such that 255+1=0 (examples given for 8-bit unsigned integers).
    # Note that -128 is 128, since 128+128=0.
    func neg(a : Uint) -> (res : Uint):
        if a.value == 0:
           return (Uint(0))
        else:
           return (Uint(SHIFT - a.value))
        end
    end
    
    
    # Conditionally negates an integer.
    # `b` below stands for `boolean`. It's a pun between "b the second argument, after a" and "b the boolean".  Programmers can be very witty.
    # We intend `b` to have value 0 (don't negate) or 1 (do negate).
    func cond_neg(a : Uint, b : felt) -> (res : Uint):
        if b != 0:
            return neg(a)
        else:
            return (a)
        end
    end

    
    # COMPARISONS
    
    # Return true if integers are equal.
    func eq(a : Uint, b : Uint) -> (res):
        if a.value != b.value:
            return (0)
        else:
            return (1)
        end
    end
    
    # Returns 1 if the first unsigned integer is less than the second unsigned integer, otherwise returns 0.
    func lt{range_check_ptr}(a : Uint, b : Uint) -> (res):
        return is_le(a.value + 1, b.value)
    end
    
    # Returns 1 if the first unsigned integer is less than or equal to the second unsigned integer, otherwise returns 0.
    func le{range_check_ptr}(a : Uint, b : Uint) -> (res):
        return is_le(a.value, b.value)
        # let (not_le) = lt(a=b, b=a) # b<a
        #    return (1 - not_le)               # ~(b<a) <=> a<=b
    end
   
 
    # BITWISE OPERATIONS (non-native on the Cairo abstract machine and therefore not as fast as you might expect of a bitwise architecture)
    
    # bitwise XOR
    func xor{range_check_ptr, bitwise_ptr : BitwiseBuiltin*}(a : Uint, b : Uint) -> (res : Uint):
        let (res_value) = bitwise_xor(a.value, b.value)
        return (Uint(res_value))
    end
    
    # bitwise OR
    func or{range_check_ptr, bitwise_ptr : BitwiseBuiltin*}(a : Uint, b : Uint) -> (res : Uint):
        let (res_value) = bitwise_or(a.value, b.value)
        return (Uint(res_value))
    end
    
    # bitwise AND
    func and{range_check_ptr, bitwise_ptr : BitwiseBuiltin*}(a : Uint, b : Uint) -> (res : Uint):
        let (res_value) = bitwise_and(a.value, b.value)
        return (Uint(res_value))
    end
    
    # Computes the logical left shift of a uint.
    # Note: "fast" bitwise operations aren't available because in the Cairo abstract machine the primitive numerical datatype is a raw field element, not a raw bitstring 
    func shl__slow{range_check_ptr}(a : Uint, b : felt) -> (res : Uint):
        let (b_is_in_range) = is_in_range(b, 0, BIT_LENGTH)
        if b_is_in_range == 1:
            let (two_pow_b) = pow(2, b)
            let (res, _) = mul(a, Uint(two_pow_b))
            return (res)
        end
        return (Uint(0))
    end
    
    # Computes the logical right shift of a uint.
    # Note: "fast" bitwise operations aren't available because in the Cairo abstract machine the primitive numerical datatype is a raw field element, not a raw bitstring 
    func shr__slow{range_check_ptr}(a : Uint, b : felt) -> (res : Uint):
        let (b_is_in_range) = is_in_range(b, 0, BIT_LENGTH)
        if b_is_in_range == 1:
            let (two_pow_b) = pow(2, b)
            let (res, _) = div_rem(a, Uint(two_pow_b))
            return (res)
        end
        return (Uint(0))
    end
    
end
# end namespace


# The code below should not be executed.  Its role is to reference the functions in the namespace above, to prevent the Cairo code optimiser from garbage-collecting the namespace's contents as dead code.
# One might call the code below a "dead code dead code eliminator eliminator", if one were inclined to dry wit.
func dead_code_dead_code_eliminator_eliminator_for_Uint10_namespace{range_check_ptr, bitwise_ptr : BitwiseBuiltin*}():
   alloc_locals
   local a : felt
   local b : felt
   let num_a = Uint10.Uint(a)
   let num_b = Uint10.Uint(b)
   Uint10.num_check{range_check_ptr=range_check_ptr}(num_a)
   Uint10.add{range_check_ptr=range_check_ptr}(num_a, num_b)
   Uint10.sub{range_check_ptr=range_check_ptr}(num_a, num_b)
   Uint10.mul{range_check_ptr=range_check_ptr}(num_a, num_b)
   Uint10.div_rem{range_check_ptr=range_check_ptr}(num_a, num_b)
   Uint10.pow2{range_check_ptr=range_check_ptr}(num_a)
   Uint10.not(num_a)
   Uint10.neg(num_a)
   Uint10.cond_neg(num_a, b)
   Uint10.eq(num_a, num_b)
   Uint10.lt{range_check_ptr=range_check_ptr}(num_a, num_b)
   Uint10.le{range_check_ptr=range_check_ptr}(num_a, num_b)
   Uint10.xor{range_check_ptr=range_check_ptr, bitwise_ptr=bitwise_ptr}(num_a, num_b)
   Uint10.or{range_check_ptr=range_check_ptr, bitwise_ptr=bitwise_ptr}(num_a, num_b)
   Uint10.and{range_check_ptr=range_check_ptr, bitwise_ptr=bitwise_ptr}(num_a, num_b)
   Uint10.shl__slow{range_check_ptr=range_check_ptr}(num_a, b)
   Uint10.shr__slow{range_check_ptr=range_check_ptr}(num_a, b)
   return()
end
