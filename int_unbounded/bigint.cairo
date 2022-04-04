# import biguint namespace from biguint file
from biguint import biguint as biguint

# Some constants
# The file should be parametric over values for BIT_LENGTH up to 125
const BIT_LENGTH = 125
const SHIFT = 2 ** 125
const EON = -1
# const NEG = -2

# Gather everything into a namespace for easier import
namespace bigint:
    # DATATYPE (STRUCT)

    # Represents an unbounded signed integer (a natural number).
    struct BigInt:
        # sign should be -1 or +1.  by convention zero can take either sign
        member sign : felt
        # this should be the magnitude of the result
        member ptr : felt*
    end

    # A valid biguint is either
    # * [EON] (representing zero) or
    # * some least dignificant digit followed by a valid biguint.
    func num_check{range_check_ptr}(a : BigInt):
        assert a.sign * a.sign = 1
        biguint.num_check(biguint.BigUint(a.ptr))
        return ()
    end

    # Calculates how many digits the absolute value of a number has, in modulo-SHIFT representation.
    # E.g. (-1, [0, 1, -1]) has two digits and represents the number -SHIFT.
    func len(a : BigInt) -> (res : felt):
        return biguint.len(biguint.BigUint(a.ptr))
    end

    # Helpful for testing
    func id(a : BigInt) -> (a : BigInt):
        return (a)
    end

    # EQUALITY

    # Verifies whether `a` denotes zero
    # Returns 0 if zero and 1 if nonzero
    func is_not_zero(a : BigInt) -> (res : felt):
        return biguint.is_not_zero(biguint.BigUint(a.ptr))
    end

    # Verifies that `a` and `b` point to arithmetically equal bigints.
    # Returns 0 if non-equal and 1 if equal
    # Could be trivially implemented using compare, but the version below should be quicker and it does not require the range_check builtin
    func is_eq(a : BigInt, b : BigInt) -> (res : felt):
        if ([a.ptr] + [b.ptr]) == -2:
            # Absolute values of a and b are both zero?  Equal!
            return (1)
        end
        if a.sign != b.sign:
            # Not both zero, and have distinct signs?  Non-equal!
            return (0)
        end
        return biguint.is_eq(biguint.BigUint(a.ptr), biguint.BigUint(b.ptr))
    end

    # Assert that `a` and `b` point to arithmetically equal biguints.
    # Fails if they don't
    # This rather brutal implementation just calls `is_eq`
    func assert_eq(a : BigInt, b : BigInt):
        let (res) = is_eq(a, b)
        assert res = 1
        return ()
    end

    # COMPARISON

    # utility function designed to be called on two biguints of equal lengh
    # returns -1 if a<b, 0 if a=b, +1 if a>b

    # Compare two biguints
    # returns -1 if a<b, 0 if a=b, +1 if a>b
    func compare{range_check_ptr}(a : BigInt, b : BigInt) -> (res : felt):
        if ([a.ptr] + [b.ptr]) == -2:
            # Absolute values of a and b are both zero?  Equal!
            return (0)
        end
        if b.sign - a.sign == 2:
            # b positive and a negative and at least one nonzero?  a < b!
            return (-1)
        end
        if a.sign - b.sign == 2:
            # a positive and b negative and at least one nonzero?  a > b!
            return (1)
        end
        # a and b have the same sign (and at least one of them is nonzero)
        # Compare |a| with |b|
        let (res_abs) = biguint.compare(biguint.BigUint(a.ptr), biguint.BigUint(b.ptr))
        # Return the sign of a multiplied by the result
        return (a.sign * res_abs)
    end

    func is_lt{range_check_ptr}(a : BigInt, b : BigInt) -> (res : felt):
        alloc_locals
        let (cmp) = compare(a, b)
        # cmp = -1 if a<b, 0 if a=b, +1 if a>b
        # ((cmp - 1) * cmp) / 2 = 1 if cmp=-1, and = 0 if cmp=0 or 1.
        return (((cmp - 1) * cmp) / 2)
    end

    func is_le{range_check_ptr}(a : BigInt, b : BigInt) -> (res : felt):
        alloc_locals
        let (cmp) = compare(b, a)
        # cmp = -1 if a>b, 0 if b=a, +1 if a<b
        # 1 - (((cmp - 1) * cmp) / 2) = 0 if cmp=-1,  = 1 if cmp=0 or 1.
        return (1 - (((cmp - 1) * cmp) / 2))
    end

    # ARITHMETIC

    func neg(a : BigInt) -> (res : BigInt):
        return (BigInt(a.sign * (-1), a.ptr))
    end

    func add{range_check_ptr}(a : BigInt, b : BigInt) -> (res : BigInt):
        let a_abs = biguint.BigUint(a.ptr)
        let b_abs = biguint.BigUint(b.ptr)
        if a.sign * b.sign == 1:
            # If a and b are both positive or both negative
            # then res=a+b has the sign of a (and of b)
            let res_sign = a.sign
            let (res_abs) = biguint.add(a_abs, b_abs)
            return (BigInt(sign=res_sign, ptr=res_abs.ptr))
        else:
            if a.sign == 1:
                # a is positive, b is negative.  a+b = |a|-|b|
                let (res_abs, res_sign) = biguint.sub(a_abs, b_abs)
            else:
                # b is positive, a is negative.  a+b = |b|-|a|
                let (res_abs, res_sign) = biguint.sub(b_abs, a_abs)
            end
            return (BigInt(sign=res_sign, ptr=res_abs.ptr))
        end
    end

    # Calculates a - b.
    func sub{range_check_ptr}(a : BigInt, b : BigInt) -> (res : BigInt):
        let (neg_b) = neg(b)
        let (a_sub_b) = add(a, neg_b)
        return (res=a_sub_b)
    end

    func mul{range_check_ptr}(a : BigInt, b : BigInt) -> (res : BigInt):
        # sign of mult is mult of signs
        let res_sign = a.sign * b.sign
        let (res_abs) = biguint.mul(biguint.BigUint(a.ptr), biguint.BigUint(b.ptr))
        return (BigInt(sign=res_sign, ptr=res_abs.ptr))
    end

    func div{range_check_ptr}(a : BigInt, b : BigInt) -> (res : BigInt, remainder : BigInt):
        # sign of div is mult of signs
        let res_sign = a.sign * b.sign
        let (res_abs, remainder_abs) = biguint.div(biguint.BigUint(a.ptr), biguint.BigUint(b.ptr))
        let res = BigInt(sign=res_sign, ptr=res_abs.ptr)
        let remainder = BigInt(sign=res_sign * b.sign, ptr=remainder_abs.ptr)
        return (res, remainder)
    end
end
# end namespace

# The code below should not be executed.  Its role is to reference the functions in the namespace above, to prevent the Cairo code optimiser from garbage-collecting the namespace's contents as dead code.
# One might call the code below a "dead code dead code eliminator eliminator", if one were inclined to dry wit.
func dead_code_dead_code_eliminator_eliminator_for_bigint_namespace{range_check_ptr}():
    alloc_locals
    local num_a : bigint.BigInt
    local num_b : bigint.BigInt
    bigint.num_check(num_a)
    bigint.id(num_a)
    bigint.len(num_a)
    bigint.is_not_zero(num_a)
    bigint.is_eq(num_a, num_b)
    bigint.assert_eq(num_a, num_b)
    bigint.compare(num_a, num_b)
    bigint.is_le(num_a, num_b)
    bigint.is_lt(num_a, num_b)
    bigint.neg(num_a)
    bigint.add(num_a, num_b)
    bigint.sub(num_a, num_b)
    bigint.mul(num_a, num_b)
    bigint.div(num_a, num_b)
    return ()
end
