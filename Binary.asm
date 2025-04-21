.data
    next_line: .asciiz "\n"
    inp_statement: .asciiz "Enter No. of integers to be taken as input: "
    inp_int_statement: .asciiz "Enter starting address of inputs(in decimal format): "
    inp_number: .asciiz "Enter the number to search for: "
    enter_int: .asciiz "Enter the number: "
    not_found: .asciiz "Number not found"
    found_statement: .asciiz "Number found at index(0 - indexing): "
.text
    

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

found: addi $t4, $s2, 0  
       j end

notfound: j end

end:  li $v0, 10
      syscall
###################################################################################################################################################




