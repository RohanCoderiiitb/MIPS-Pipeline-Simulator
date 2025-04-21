.data
    # No input/output strings needed

.text
 
# Hardcode the first number in $a0
addi $a0, $0, 7  

# Hardcode the second number in $a1
addi $a1, $0, 13   

# Initialize shift to 0
addi $a2, $0, 0

# Call the recursive GCD function
jal recursive_gcd

# Result is now in $v0, shift by $v1
sllv $v0, $v0, $v1       
addi $t4, $v0, 0        # Store final result in $t4

# End program
nop

######################################################################################################
# Recursive function for Stein's Algorithm GCD
# Parameters: $a0 = a, $a1 = b, $a2 = shift
# Returns: GCD in $v0, shift in $v1

recursive_gcd:
    # Save return address and registers on stack
    addi $sp, $sp, -16
    sw $ra, 0($sp)
    sw $s0, 4($sp)
    sw $s1, 8($sp)
    sw $s2, 12($sp)
    
    # Copy parameters to preserved registers
    add $s0, $a0, $0    # s0 = a
    add $s1, $a1, $0    # s1 = b
    add $s2, $a2, $0    # s2 = shift
    
    # Base case 1: If a is zero, return b
    bne $s0, $0, not_a_zero
    add $v0, $s1, $0     # Return b as result
    add $v1, $s2, $0     # Return shift
    j gcd_return

not_a_zero:
    # Base case 2: If b is zero, return a
    bne $s1, $0, not_b_zero
    add $v0, $s0, $0     # Return a as result
    add $v1, $s2, $0     # Return shift
    j gcd_return

not_b_zero:
    # Check if both a and b are even
    or $t0, $s0, $s1    
    andi $t0, $t0, 1   
    bne $t0, $0, not_both_even

    # Both numbers are even
    srl $s0, $s0, 1        
    srl $s1, $s1, 1       
    addi $s2, $s2, 1      
    
    # Recursive call with updated values
    add $a0, $s0, $0
    add $a1, $s1, $0
    add $a2, $s2, $0
    jal recursive_gcd
    
    # Result is already in $v0/$v1
    j gcd_return

not_both_even:
    # Check if a is even
    andi $t0, $s0, 1
    bne $t0, $0, not_a_even

    # a is even, b is odd
    srl $s0, $s0, 1        
    
    # Recursive call with updated values
    add $a0, $s0, $0
    add $a1, $s1, $0
    add $a2, $s2, $0
    jal recursive_gcd
    
    # Result is already in $v0/$v1
    j gcd_return

not_a_even:
    # Check if b is even
    andi $t0, $s1, 1
    bne $t0, $0, both_odd

    # a is odd, b is even
    srl $s1, $s1, 1        
    
    # Recursive call with updated values
    add $a0, $s0, $0
    add $a1, $s1, $0
    add $a2, $s2, $0
    jal recursive_gcd
    
    # Result is already in $v0/$v1
    j gcd_return

both_odd:
    # Both a and b are odd
    slt $t0, $s0, $s1
    beq $t0, $0, a_greater_equal_b
    
    # a < b: subtract a from b
    sub $s1, $s1, $s0
    
    # Recursive call with updated values
    add $a0, $s0, $0
    add $a1, $s1, $0
    add $a2, $s2, $0
    jal recursive_gcd
    
    # Result is already in $v0/$v1
    j gcd_return
    
a_greater_equal_b:
    # a >= b: subtract b from a
    sub $s0, $s0, $s1
    
    # Recursive call with updated values
    add $a0, $s0, $0
    add $a1, $s1, $0
    add $a2, $s2, $0
    jal recursive_gcd
    
    # Result is already in $v0/$v1
    j gcd_return

gcd_return:
    # Restore saved registers
    lw $ra, 0($sp)
    lw $s0, 4($sp)
    lw $s1, 8($sp)
    lw $s2, 12($sp)
    addi $sp, $sp, 16
    
    # Return to caller
    jr $ra