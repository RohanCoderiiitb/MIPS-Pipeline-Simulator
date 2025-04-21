        .text
        .globl main

# main: set up two values in $a0 and $a1 and call binary_gcd
main:
        # hard‑coded inputs; change these to test other values
        li   $a0, 56        # first number
        li   $a1, 98        # second number
        jal  binary_gcd
        # result in $v0
        j    done

# binary_gcd(a0 = x, a1 = y) -> v0 = gcd(x,y)
# recursive Stein’s algorithm
binary_gcd:
        addi  $sp, $sp, -8   # allocate stack frame
        sw    $ra, 4($sp)
        sw    $s0, 0($sp)

        move  $s0, $a0       # s0 = x
        move  $s1, $a1       # s1 = y

        # base cases
        beq   $s0, $s1, ret_equal
        beq   $s0, $zero, ret_y
        beq   $s1, $zero, ret_x

        # both even?
        andi  $t0, $s0, 1
        andi  $t1, $s1, 1
        beq   $t0, $zero, x_even
not_both_even:
        # x odd, y odd
        blt   $s0, $s1, x_less
        # x > y
        sub   $a0, $s0, $s1
        sra   $a0, $a0, 1
        move  $a1, $s1
        j     recurse
x_less:
        sub   $a0, $s1, $s0
        sra   $a0, $a0, 1
        move  $a1, $s0
        j     recurse

x_even:
        # x even
        beq   $t1, $zero, both_even
        # y odd
        sra   $a0, $s0, 1
        move  $a1, $s1
        j     recurse
both_even:
        # both even: gcd(x/2, y/2) << 1
        sra   $a0, $s0, 1
        sra   $a1, $s1, 1
        jal   binary_gcd
        sll   $v0, $v0, 1
        j     epilogue

recurse:
        jal   binary_gcd   # returns in $v0
        move  $v0, $v0

        j    epilogue

# returns when x == y
ret_equal:
        move  $v0, $s0
        j    epilogue

# returns y when x == 0
ret_y:
        move  $v0, $s1
        j    epilogue

# returns x when y == 0
ret_x:
        move  $v0, $s0

epilogue:
        lw    $s0, 0($sp)
        lw    $ra, 4($sp)
        addi  $sp, $sp, 8
        jr    $ra

done:
        j    done          # infinite loop
