.data
    # No input/output strings needed

.text
 
# Hardcode the first number (13) in $t1
addi $t1, $0, 13      

# Hardcode the second number (7) in $t2
addi $t2, $0, 7       

# Initialize shift to 0
addi $t3, $0, 0

# Call the recursive GCD function
jal recursive_gcd

# Result is now in $t1, shift by $t3
sllv $t1, $t1, $t3       
addi $t4, $t1, 0        

# End program
nop

######################################################################################################
# Recursive function for Stein's Algorithm GCD
# Parameters: $t1 = a, $t2 = b, $t3 = shift
# Returns: GCD in $t1, shift in $t3

recursive_gcd:
    # Base case 1: If a is zero, return b
    beq $t1, $0, return_b

    # Base case 2: If b is zero, return a
    beq $t2, $0, return_a

    # Check if both a and b are even
    or $t5, $t1, $t2    
    andi $t5, $t5, 1   
    beq $t5, $0, both_even

    # Check if a is even
    andi $t5, $t1, 1
    beq $t5, $0, a_even

    # Check if b is even
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