.data
    next_line: .asciiz "\n"
    First_Number: .asciiz "Enter the first number: "
    Second_Number: .asciiz "Enter the second Number: "
    Output_statement: .asciiz "The GCD of the two numbers is: "
.text            

# End program
end:  li $v0, 10
      syscall

######################################################################################################
# Recursive function for Stein's Algorithm GCD
# Parameters: $t1 = a, $t2 = b, $t3 = shift
# Recursively computes the GCD of $t1 and $t2

recursive_gcd:
    # Base case 1: If a is zero, return b
    beq $t1, $0, return_b

    # Base case 2: If b is zero, return a
    beq $t2, $0, return_a

    # Check if both a and b are even
    or $t5, $t1, $t2    
    andi $t5, $t5, 1   
    beq $t5, $0, both_even

    # a is even
    andi $t5, $t1, 1
    beq $t5, $0, a_even

    # b is even
    andi $t5, $t2, 1
    beq $t5, $0, b_even

    # Both a and b are odd
    ble $t1, $t2, subtract_b_a
    sub $t1, $t1, $t2
    j recursive_gcd

subtract_b_a:
    sub $t2, $t2, $t1
    j recursive_gcd

# Case: Both numbers are even
both_even:
    srl $t1, $t1, 1        
    srl $t2, $t2, 1       
    addi $t3, $t3, 1      
    j recursive_gcd

# Case: a is even, b is odd
a_even:
    srl $t1, $t1, 1        
    j recursive_gcd

# Case: a is odd, b is even
b_even:
    srl $t2, $t2, 1        
    j recursive_gcd

# Return value of b (GCD)
return_b:
    addi $t1, $t2, 0       
    jr $ra

# Return value of a (GCD)
return_a:
    jr $ra

######################################################################################################
