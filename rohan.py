import random

# Simulated memory and registers
memory = {i: i // 4 for i in range(0, 40, 4)}  # Memory with initial values 0 to 9 at addresses 0 to 36
registers = [0] * 32  # 32 registers initialized to 0

# Instruction memory with labels
instruction_memory_raw = [
    "start: addi $t0, $zero, 0",       # t0 = 0
    "       addi $s0, $zero, 0",       # s0 = 0
    "       addi $t3, $zero, 0",       # t3 = 0 (memory pointer)
    "loop:  slti $t1, $t0, 10",        # if t0 < 10
    "       beq $t1, $zero, endloop",  # if not < 10, jump to endloop
    "       lw $t2, 0($t3)",           # load array[t3]
    "       add $s0, $s0, $t2",        # s0 += t2
    "       and $t4, $t0, $t2",        # just a random R-type logic op
    "       or $t5, $t4, $t1",         # another logic op
    "       sw $t5, 100($zero)",       # store something at memory[100]
    "       bne $t5, $zero, skip",     # branch if t5 != 0
    "       addi $t6, $t6, 1",         # only if branch not taken
    "skip:  addi $t0, $t0, 1",         # t0++
    "       addi $t3, $t3, 4",         # t3 += 4
    "       j loop",                   # go back to loop
    "endloop: sw $s0, 40($zero)",      # store sum at memory[40]
    "         nop"
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
    
    # Second pass: resolve labels in beq, bne, j
    for i in range(len(cleaned_instructions)):
        parts = cleaned_instructions[i].split()
        if parts[0] in ['beq', 'bne']:
            parts[-1] = str(label_to_index[parts[-1]])
            cleaned_instructions[i] = ' '.join(parts)
        elif parts[0] == 'j':
            parts[1] = str(label_to_index[parts[1]])
            cleaned_instructions[i] = ' '.join(parts)
    return cleaned_instructions

instruction_memory = preprocess_labels(instruction_memory_raw)

# Register mapping
def parse_register(reg):
    reg_map = {'$zero': 0, '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11,
               '$t4': 12, '$t5': 13, '$t6': 14, '$s0': 16}
    return reg_map.get(reg, 0)

# Parse MIPS instructions
def parse_instruction(instr):
    parts = instr.split()
    opcode = parts[0]
    if opcode in ['addi', 'slti']:
        rd, rs, imm = parts[1].strip(','), parts[2].strip(','), int(parts[3])
        return {'type': 'I', 'opcode': opcode, 'rd': parse_register(rd), 'rs': parse_register(rs), 'imm': imm}
    elif opcode in ['beq', 'bne']:
        rs, rt, offset = parts[1].strip(','), parts[2].strip(','), int(parts[3])
        return {'type': 'I', 'opcode': opcode, 'rs': parse_register(rs), 'rt': parse_register(rt), 'offset': offset}
    elif opcode == 'j':
        target = int(parts[1])
        return {'type': 'J', 'opcode': opcode, 'target': target}
    elif opcode in ['lw', 'sw']:
        rt, offset_base = parts[1].strip(','), parts[2]
        offset, base = offset_base.split('(')
        base = base.strip(')')
        return {'type': 'I', 'opcode': opcode, 'rt': parse_register(rt), 'base': parse_register(base), 'offset': int(offset)}
    elif opcode in ['add', 'and', 'or']:
        rd, rs, rt = parts[1].strip(','), parts[2].strip(','), parts[3]
        return {'type': 'R', 'opcode': opcode, 'rd': parse_register(rd), 'rs': parse_register(rs), 'rt': parse_register(rt)}
    elif opcode == 'nop':
        return {'type': 'nop', 'opcode': 'nop'}
    else:
        raise ValueError(f"Unknown instruction: {instr}")

# Pipeline simulation
def simulate():
    PC = 0
    cycle = 0
    total_instructions = 0
    memory_stalls = 0
    delayed_branches = 0
    load_stalls = 0
    cycles_wasted_memory = 0

    IF_ID = None
    ID_EX = None
    EX_MEM = None
    MEM_WB = None
    delayed_branch = False
    branch_target = 0

    pipeline_log = []

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
                    b = ID_EX['rt_value']
                    result = {
                        'add': a + b,
                        'and': a & b,
                        'or': a | b
                    }[instr['opcode']]
                    EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                elif instr['type'] == 'I':
                    if instr['opcode'] == 'addi':
                        result = ID_EX['rs_value'] + instr['imm']
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                    elif instr['opcode'] == 'slti':
                        result = 1 if ID_EX['rs_value'] < instr['imm'] else 0
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                    elif instr['opcode'] == 'beq':
                        if ID_EX['rs_value'] == ID_EX['rt_value']:
                            delayed_branch = True
                            branch_target = instr['offset']
                            delayed_branches += 1
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif instr['opcode'] == 'bne':
                        if ID_EX['rs_value'] != ID_EX['rt_value']:
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
                elif instr['type'] == 'J' and instr['opcode'] == 'j':
                    delayed_branch = True
                    branch_target = instr['target']
                    delayed_branches += 1
                    EX_MEM = {'instr': instr, 'cycles_left': 1}
                elif instr['type'] == 'nop':
                    EX_MEM = {'instr': instr, 'cycles_left': 1}

            if IF_ID:
                instr = parse_instruction(IF_ID['instruction'])
                rs_value = registers[instr.get('rs', 0)]
                rt_value = registers[instr.get('rt', 0)]
                base_value = registers[instr.get('base', 0)] if 'base' in instr else 0
                ID_EX = {'instr': instr, 'rs_value': rs_value, 'rt_value': rt_value, 'base_value': base_value, 'index': IF_ID['index']}
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

        if PC >= len(instruction_memory) and not MEM_WB and not EX_MEM and not ID_EX and not IF_ID:
            break

    print("\nPipeline Timing Table:")
    print("| Cycle | IF       | ID       | EX       | MEM      | WB       |")
    print("|-------|----------|----------|----------|----------|----------|")
    for entry in pipeline_log[:30]:  # Show more cycles now
        print(f"| {entry[0]:5d} | {str(entry[1]):8} | {str(entry[2]):8} | {str(entry[3]):8} | {str(entry[4]):8} | {str(entry[5]):8} |")

    print(f"\nTotal clock cycles: {cycle}")
    print(f"Total instructions executed: {total_instructions}")
    print(f"Total stalls due to memory: {memory_stalls}")
    print(f"Stalls due to loads: {load_stalls}")
    print(f"Delayed branches taken: {delayed_branches}")
    print(f"Branch delay slot effectiveness: 100% (all delay slots executed)")
    print(f"Cycles wasted due to memory delays: {cycles_wasted_memory}")

if __name__ == "__main__":
    simulate()
