.data
    next_line: .asciiz "\n"
    inp_statement: .asciiz "Enter No. of integers to be taken as input: "
    inp_int_statement: .asciiz "Enter starting address of inputs(in decimal format): "
    inp_number: .asciiz "Enter the number to search for: "
    enter_int: .asciiz "Enter the number: "
    not_found: .asciiz "Number not found"
    found_statement: .asciiz "Number found at index(0 - indexing): "
.text

    jal print_inp_statement    
    jal input_int 
    addi $t1, $t4, 0        

    jal print_inp_int_statement
    jal input_int
    addi $t2, $t4, 0         

    addi $t8, $t2, 0        
    addi $s7,$0, 0       

loop:  beq $s7, $t1, loop1end
       jal print_enter_int
       jal input_int
       sw $t4, 0($t2)
       addi $t2, $t2, 4
       addi $s7, $s7, 1
       j loop     
loop1end: addi $t2, $t8, 0    

# Input: The number to be searched for is entered from terminal.
    jal print_inp_number
    jal input_int
    addi $s5, $t4, 0        

#################################################################################################################################################
# $t1 = N
# $t2 = Starting address of input numbers
# $s5 = Number to be searched for

    addi $s0,$0, 0      # left = 0
    addi $s1, $t1, -1   # right = N-1
    addi $s2,$0, 0      # mid = 0

loop1: slt $t5, $s1, $s0
       bne $t5,$0, notfound
       sub $t3, $s1, $s0
       srl $t3, $t3, 1
       add $s2, $s0, $t3
       sll $t7, $s2, 2      
       add $t6, $t2, $t7    
       lw $t6, 0($t6)      

       beq $t6, $s5, found
       slt $t5, $t6, $s5
cond1: beq $t5,$0, cond2
       addi $s0, $s2, 1
       j loop1
cond2: addi $s1, $s2, -1
       j loop1

found: jal print_found
       addi $t4, $s2, 0  
       jal print_int
       j end

notfound: jal print_not_found
          j end

end:  li $v0, 10
      syscall
###################################################################################################################################################

# Input from command line (takes input and stores it in $t4)
input_int: li $v0, 5
           syscall
           addi $t4, $v0, 0   
           jr $ra

# Print integer (prints the value of $t4)
print_int: li $v0, 1   
           addi $a0, $t4, 0  
           syscall
           jr $ra

# Print nextline
print_line: li $v0, 4
            la $a0, next_line
            syscall
            jr $ra

# Print number of inputs statement
print_inp_statement: li $v0, 4
                     la $a0, inp_statement
                     syscall 
                     jr $ra

# Print input address statement
print_inp_int_statement: li $v0, 4
                         la $a0, inp_int_statement
                         syscall 
                         jr $ra

# Print enter integer statement
print_enter_int: li $v0, 4
                 la $a0, enter_int
                 syscall 
                 jr $ra

# Print not found statement
print_not_found: li $v0, 4
                 la $a0, not_found
                 syscall 
                 jr $ra

# Print found statement
print_found: li $v0, 4
             la $a0, found_statement
             syscall 
             jr $ra

# Print inp_number statement
print_inp_number: li $v0, 4
                  la $a0, inp_number
                  syscall 
                  jr $ra


