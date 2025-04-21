import random
import time
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)

# Simulated memory and registers
memory = {i: i // 4 for i in range(0, 40, 4)}  # Memory with initial values 0 to 9 at addresses 0 to 36
registers = [0] * 32  # 32 registers initialized to 0

# Instruction memory with labels
instruction_memory_raw = [
    "start: addi $t0, $zero, 0",       # t0 = 0
    "       addi $s0, $zero, 0",       # s0 = 0
    "       addi $t3, $zero, 0",       # t3 = 0 (memory pointer)
    "       addi $t7, $zero, 100",     # t7 = 100 (constant for later use)
    "loop:  slti $t1, $t0, 10",        # if t0 < 10
    "       beq $t1, $zero, endloop",  # if not < 10, jump to endloop
    "       lw $t2, 0($t3)",           # load array[t3]
    "       add $s0, $s0, $t2",        # s0 += t2
    "       and $t4, $t0, $t2",        # just a random R-type logic op
    "       or $t5, $t4, $t1",         # another logic op
    "       sw $t5, 100($zero)",       # store something at memory[100]
    "       bne $t5, $zero, skip",     # branch if t5 != 0
    "       addi $t6, $t6, 1",         # only if branch not taken
    "skip:  sub $t8, $t7, $t0",        # t8 = 100 - t0
    "       sll $t9, $t0, 2",          # t9 = t0 * 4
    "       slt $s1, $t0, $t2",        # s1 = (t0 < t2) ? 1 : 0
    "       beq $s1, $zero, noskip",   # branch if s1 == 0
    "       addi $s2, $s2, 1",         # increment s2 if branch taken
    "noskip: jal helper",              # call helper function
    "        addi $s3, $s3, 1",        # delay slot for jal
    "        addi $t0, $t0, 1",        # t0++
    "        addi $t3, $t3, 4",        # t3 += 4
    "        j loop",                  # go back to loop
    "helper: mult $t0, $t2",           # multiply t0 and t2 (hi/lo not shown)
    "        mfhi $s4",                # move from hi
    "        mflo $s5",                # move from lo
    "        jr $ra",                  # return
    "endloop: sw $s0, 40($zero)",      # store sum at memory[40]
    "         lw $s6, 40($zero)",      # load it back
    "         xor $s7, $s6, $s0",      # should be 0
    "         bgez $s7, error",        # if not 0, error
    "         nop",                    # delay slot
    "         j exit",                 # normal exit
    "error:  addi $v0, $zero, 1",      # set error code
    "exit:   nop"
]

# Convert label-based instructions to indexed instruction memory
def preprocess_labels(instrs):
    label_to_index = {}
    cleaned_instructions = []

    for index, line in enumerate(instrs):
        line = line.strip()
        if ':' in line:
            label, rest = line.split(':', 1)
            label = label.strip()
            rest = rest.strip()
            label_to_index[label] = len(cleaned_instructions)
            if rest:
                cleaned_instructions.append(rest)
        else:
            cleaned_instructions.append(line)
    
    # Second pass: resolve labels in beq, bne, j, jal
    for i in range(len(cleaned_instructions)):
        parts = cleaned_instructions[i].split()
        if parts[0] in ['beq', 'bne', 'bgez', 'bltz']:
            parts[-1] = str(label_to_index[parts[-1]])
            cleaned_instructions[i] = ' '.join(parts)
        elif parts[0] in ['j', 'jal']:
            parts[1] = str(label_to_index[parts[1]])
            cleaned_instructions[i] = ' '.join(parts)
    return cleaned_instructions

instruction_memory = preprocess_labels(instruction_memory_raw)

# Complete register mapping for all 32 MIPS registers
def parse_register(reg):
    reg_map = {
        '$zero': 0, '$at': 1, '$v0': 2, '$v1': 3,
        '$a0': 4, '$a1': 5, '$a2': 6, '$a3': 7,
        '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11,
        '$t4': 12, '$t5': 13, '$t6': 14, '$t7': 15,
        '$s0': 16, '$s1': 17, '$s2': 18, '$s3': 19,
        '$s4': 20, '$s5': 21, '$s6': 22, '$s7': 23,
        '$t8': 24, '$t9': 25, '$k0': 26, '$k1': 27,
        '$gp': 28, '$sp': 29, '$fp': 30, '$ra': 31
    }
    return reg_map.get(reg, 0)

# Parse MIPS instructions with more instruction types
def parse_instruction(instr):
    parts = instr.split()
    opcode = parts[0]
    
    if opcode in ['addi', 'slti']:
        rd, rs, imm = parts[1].strip(','), parts[2].strip(','), int(parts[3])
        return {'type': 'I', 'opcode': opcode, 'rd': parse_register(rd), 'rs': parse_register(rs), 'imm': imm}
    elif opcode in ['beq', 'bne']:
        rs, rt, offset = parts[1].strip(','), parts[2].strip(','), int(parts[3])
        return {'type': 'I', 'opcode': opcode, 'rs': parse_register(rs), 'rt': parse_register(rt), 'offset': offset}
    elif opcode in ['bgez', 'bltz']:
        rs, offset = parts[1].strip(','), int(parts[2])
        return {'type': 'I', 'opcode': opcode, 'rs': parse_register(rs), 'offset': offset}
    elif opcode in ['j', 'jal']:
        target = int(parts[1])
        return {'type': 'J', 'opcode': opcode, 'target': target}
    elif opcode == 'jr':
        rs = parts[1]
        return {'type': 'R', 'opcode': opcode, 'rs': parse_register(rs)}
    elif opcode in ['lw', 'sw']:
        rt, offset_base = parts[1].strip(','), parts[2]
        offset, base = offset_base.split('(')
        base = base.strip(')')
        return {'type': 'I', 'opcode': opcode, 'rt': parse_register(rt), 'base': parse_register(base), 'offset': int(offset)}
    elif opcode in ['add', 'sub', 'and', 'or', 'xor', 'slt', 'sll', 'srl']:
        if len(parts) == 4:
            rd, rs, rt = parts[1].strip(','), parts[2].strip(','), parts[3]
            return {'type': 'R', 'opcode': opcode, 'rd': parse_register(rd), 'rs': parse_register(rs), 'rt': parse_register(rt)}
        elif len(parts) == 3:  # for shift instructions like sll
            rd, rt, shamt = parts[1].strip(','), parts[2].strip(','), int(parts[3])
            return {'type': 'R', 'opcode': opcode, 'rd': parse_register(rd), 'rt': parse_register(rt), 'shamt': shamt}
    elif opcode in ['mult', 'div']:
        rs, rt = parts[1].strip(','), parts[2]
        return {'type': 'R', 'opcode': opcode, 'rs': parse_register(rs), 'rt': parse_register(rt)}
    elif opcode in ['mfhi', 'mflo']:
        rd = parts[1]
        return {'type': 'R', 'opcode': opcode, 'rd': parse_register(rd)}
    elif opcode == 'nop':
        return {'type': 'nop', 'opcode': 'nop'}
    else:
        raise ValueError(f"Unknown instruction: {instr}")

# Color coding for different stages
def color_stage(stage, text):
    if text is None:
        return Fore.WHITE + " " * 8
    colors = {
        'IF': Fore.BLUE,
        'ID': Fore.CYAN,
        'EX': Fore.GREEN,
        'MEM': Fore.YELLOW,
        'WB': Fore.MAGENTA
    }
    return colors.get(stage, Fore.WHITE) + f"{text:8}" + Style.RESET_ALL

# Corrected and improved code

def simulate():
    PC = 0
    cycle = 0
    total_instructions = 0
    memory_stalls = 0
    delayed_branches = 0
    load_stalls = 0
    cycles_wasted_memory = 0
    branch_mispredictions = 0

    IF_ID = None
    ID_EX = None
    EX_MEM = None
    MEM_WB = None
    delayed_branch = False
    branch_target = 0

    pipeline_log = []

    # Special registers for mult/div
    hi = 0
    lo = 0

    while True:
        cycle += 1
        current_stage = {'IF': None, 'ID': None, 'EX': None, 'MEM': None, 'WB': None}

        # WB stage
        if MEM_WB:
            instr = MEM_WB['instr']
            if 'rd' in instr:
                registers[instr['rd']] = MEM_WB.get('result', 0)
            elif 'rt' in instr and instr['opcode'] == 'lw':
                registers[instr['rt']] = MEM_WB.get('result', 0)
            elif instr['opcode'] == 'mfhi':
                registers[instr['rd']] = hi
            elif instr['opcode'] == 'mflo':
                registers[instr['rd']] = lo
            total_instructions += 1
            current_stage['WB'] = instr['opcode']

        # MEM stage
        stall = False
        if EX_MEM and EX_MEM['cycles_left'] > 1:
            EX_MEM['cycles_left'] -= 1
            memory_stalls += 1
            cycles_wasted_memory += 1
            if EX_MEM['instr']['opcode'] == 'lw':
                load_stalls += 1
            stall = True
            current_stage['MEM'] = f"{EX_MEM['instr']['opcode']} ({EX_MEM['cycles_left']})"
        else:
            current_stage['MEM'] = EX_MEM['instr']['opcode'] if EX_MEM else None

        if not stall:
            MEM_WB = EX_MEM
            EX_MEM = None

            if ID_EX:
                instr = ID_EX['instr']
                current_stage['EX'] = instr['opcode']
                if instr['type'] == 'R':
                    a = ID_EX['rs_value']
                    b = ID_EX.get('rt_value', 0)
                    shamt = instr.get('shamt', 0)
                    
                    if instr['opcode'] == 'jr':
                        delayed_branch = True
                        branch_target = a
                        delayed_branches += 1
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif instr['opcode'] == 'mult':
                        result = a * b
                        hi = (result >> 32) & 0xFFFFFFFF
                        lo = result & 0xFFFFFFFF
                        EX_MEM = {'instr': instr, 'cycles_left': 10}  # mult takes longer
                    elif instr['opcode'] == 'div':
                        if b != 0:
                            lo = a // b
                            hi = a % b
                        EX_MEM = {'instr': instr, 'cycles_left': 20}  # div takes even longer
                    else:
                        result = {
                            'add': a + b,
                            'sub': a - b,
                            'and': a & b,
                            'or': a | b,
                            'xor': a ^ b,
                            'slt': 1 if a < b else 0,
                            'sll': b << shamt,
                            'srl': b >> shamt
                        }.get(instr['opcode'], 0)
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                elif instr['type'] == 'I':
                    if instr['opcode'] == 'addi':
                        result = ID_EX['rs_value'] + instr['imm']
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                    elif instr['opcode'] == 'slti':
                        result = 1 if ID_EX['rs_value'] < instr['imm'] else 0
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                    elif instr['opcode'] in ['beq', 'bne']:
                        if ((instr['opcode'] == 'beq' and ID_EX['rs_value'] == ID_EX['rt_value']) or \
                           (instr['opcode'] == 'bne' and ID_EX['rs_value'] != ID_EX['rt_value'])):
                            delayed_branch = True
                            branch_target = instr['offset']
                            delayed_branches += 1
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif instr['opcode'] in ['bgez', 'bltz']:
                        if (instr['opcode'] == 'bgez' and ID_EX['rs_value'] >= 0) or \
                           (instr['opcode'] == 'bltz' and ID_EX['rs_value'] < 0):
                            delayed_branch = True
                            branch_target = instr['offset']
                            delayed_branches += 1
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif instr['opcode'] == 'lw':
                        address = ID_EX['base_value'] + instr['offset']
                        result = memory.get(address, 0)
                        EX_MEM = {'instr': instr, 'cycles_left': 2, 'result': result}
                    elif instr['opcode'] == 'sw':
                        address = ID_EX['base_value'] + instr['offset']
                        memory[address] = ID_EX['rt_value']
                        EX_MEM = {'instr': instr, 'cycles_left': 3}
                elif instr['type'] == 'J':
                    if instr['opcode'] in ['j', 'jal']:
                        delayed_branch = True
                        branch_target = instr['target']
                        delayed_branches += 1
                        if instr['opcode'] == 'jal':
                            registers[31] = ID_EX['index'] + 1  # $ra = return address
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                elif instr['type'] == 'nop':
                    EX_MEM = {'instr': instr, 'cycles_left': 1}

            if IF_ID:
                instr = parse_instruction(IF_ID['instruction'])
                rs_value = registers[instr.get('rs', 0)]
                rt_value = registers[instr.get('rt', 0)]
                base_value = registers[instr.get('base', 0)] if 'base' in instr else 0
                ID_EX = {'instr': instr, 'rs_value': rs_value, 'rt_value': rt_value, 
                        'base_value': base_value, 'index': IF_ID['index']}
                current_stage['ID'] = instr['opcode']
            else:
                ID_EX = None

            if PC < len(instruction_memory) and not stall:
                IF_ID = {'instruction': instruction_memory[PC], 'index': PC}
                current_stage['IF'] = instruction_memory[PC].split()[0]
                if delayed_branch:
                    PC = branch_target
                    delayed_branch = False
                else:
                    PC += 1
            else:
                IF_ID = None

        pipeline_log.append([cycle] + [current_stage[stage] for stage in ['IF', 'ID', 'EX', 'MEM', 'WB']])

        # Display the pipeline diagram with colors and delay
        if cycle <= 30:  # Only show first 30 cycles for brevity
            time.sleep(0.3)  # Delay between cycles
            print("\n" + Fore.WHITE + f"Cycle {cycle}:")
            print("+" + "-"*10 + "+" + "-"*12 + "+" + "-"*12 + "+" + "-"*12 + "+" + "-"*12 + "+")
            print("|" + Fore.BLUE + " IF".center(10) + "|" + Fore.CYAN + " ID".center(12) + "|" + 
                  Fore.GREEN + " EX".center(12) + "|" + Fore.YELLOW + " MEM".center(12) + "|" + 
                  Fore.MAGENTA + " WB".center(12) + "|")
            print("+" + "-"*10 + "+" + "-"*12 + "+" + "-"*12 + "+" + "-"*12 + "+" + "-"*12 + "+")
            print("|" + color_stage('IF', current_stage['IF']) + "|" + 
                  color_stage('ID', current_stage['ID']) + "|" + 
                  color_stage('EX', current_stage['EX']) + "|" + 
                  color_stage('MEM', current_stage['MEM']) + "|" + 
                  color_stage('WB', current_stage['WB']) + "|")
            print("+" + "-"*10 + "+" + "-"*12 + "+" + "-"*12 + "+" + "-"*12 + "+" + "-"*12 + "+")

        if PC >= len(instruction_memory) and not MEM_WB and not EX_MEM and not ID_EX and not IF_ID:
            break

    print("\nFinal Statistics:")
    print(f"Total clock cycles: {cycle}")
    print(f"Total instructions executed: {total_instructions}")
    print(f"Total stalls due to memory: {memory_stalls}")
    print(f"Stalls due to loads: {load_stalls}")
    print(f"Delayed branches taken: {delayed_branches}")
    print(f"Branch delay slot effectiveness: {100 * delayed_branches / max(1, total_instructions):.2f}%")
    print(f"Cycles wasted due to memory delays: {cycles_wasted_memory}")
    print(f"Branch mispredictions: {branch_mispredictions}")
    
    print("\nFinal Register State:")
    for i in range(0, 32, 4):
        print(f"R{i:2}: {registers[i]:5} | R{i+1:2}: {registers[i+1]:5} | " +
              f"R{i+2:2}: {registers[i+2]:5} | R{i+3:2}: {registers[i+3]:5}")

if __name__ == "__main__":
    simulate()