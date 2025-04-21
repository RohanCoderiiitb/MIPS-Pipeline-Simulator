.data
    array: .word 1, 2, 3, 4, 5  # Hardcoded array values
    # No input/output strings needed anymore

.text
    # Initialize values
    addi $t1, $0, 5         # N = 5 (size of array)
    la $t2, array           # Load address of array
    addi $s5, $0, 3         # Number to search for = 3

    # Binary search implementation
    addi $s0, $0, 0         # left = 0
    addi $s1, $t1, -1       # right = N-1
    addi $s2, $0, 0         # mid = 0

loop1: slt $t5, $s1, $s0    # Check if right < left
       bne $t5, $0, notfound
       sub $t3, $s1, $s0    # Calculate (right - left)
       srl $t3, $t3, 1      # Divide by 2
       add $s2, $s0, $t3    # mid = left + (right - left)/2
       sll $t7, $s2, 2      # mid * 4 (word offset)
       add $t6, $t2, $t7    # Get address of array[mid]
       lw $t6, 0($t6)       # Load value at array[mid]

       beq $t6, $s5, found  # Check if array[mid] == target
       slt $t5, $t6, $s5    # Check if array[mid] < target
cond1: beq $t5, $0, cond2
       addi $s0, $s2, 1     # left = mid + 1
       j loop1
cond2: addi $s1, $s2, -1    # right = mid - 1
       j loop1

found: addi $t4, $s2, 0     # Store result in $t4 (index where found)
       j end

notfound: addi $t4, $0, -1  # Store -1 in $t4 (not found)
          j end

end:  nop                   # End of program - result is in $t4
      # Replace syscall with nop