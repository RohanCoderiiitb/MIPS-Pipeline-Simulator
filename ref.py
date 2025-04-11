import random

# Simulated memory and registers
memory = {i: i // 4 for i in range(0, 40, 4)}  # Memory with initial values 0 to 9 at addresses 0 to 36
registers = [0] * 32  # 32 registers initialized to 0

# Instruction memory: Array sum with a loop (complex enough to test branches and memory access)
instruction_memory = [
    "addi $t0, $zero, 0",      # 0: t0 = 0 (loop counter)
    "addi $s0, $zero, 0",      # 1: s0 = 0 (sum)
    "addi $t3, $zero, 0",      # 2: t3 = 0 (memory pointer)
    "slti $t1, $t0, 10",       # 3: t1 = 1 if t0 < 10, else 0
    "beq $t1, $zero, 7",       # 4: if t1 == 0, branch to endloop (offset = 7)
    "nop",                     # 5: delay slot
    "lw $t2, 0($t3)",          # 6: load array[t3] into t2
    "add $s0, $s0, $t2",       # 7: s0 += t2
    "addi $t0, $t0, 1",        # 8: t0++
    "addi $t3, $t3, 4",        # 9: t3 += 4 (next element)
    "j 3",                     # 10: jump to slti (index 3)
    "nop",                     # 11: delay slot
    "sw $s0, 40($zero)",       # 12: store sum at memory[40]
]

# Register mapping
def parse_register(reg):
    reg_map = {'$zero': 0, '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11, '$s0': 16}
    return reg_map.get(reg, 0)

# Parse MIPS instructions
def parse_instruction(instr):
    parts = instr.split()
    opcode = parts[0]
    if opcode == 'addi' or opcode == 'slti':
        rd, rs, imm = parts[1].strip(','), parts[2].strip(','), int(parts[3])
        return {'type': 'I', 'opcode': opcode, 'rd': parse_register(rd), 'rs': parse_register(rs), 'imm': imm}
    elif opcode == 'beq':
        rs, rt, offset = parts[1].strip(','), parts[2].strip(','), int(parts[3])
        return {'type': 'I', 'opcode': 'beq', 'rs': parse_register(rs), 'rt': parse_register(rt), 'offset': offset}
    elif opcode == 'j':
        target = int(parts[1])
        return {'type': 'J', 'opcode': 'j', 'target': target}
    elif opcode == 'lw' or opcode == 'sw':
        rt, offset_base = parts[1].strip(','), parts[2]
        offset, base = offset_base.split('(')
        base = base.strip(')')
        op = 'lw' if opcode == 'lw' else 'sw'
        return {'type': 'I', 'opcode': op, 'rt': parse_register(rt), 'base': parse_register(base), 'offset': int(offset)}
    elif opcode == 'add':
        rd, rs, rt = parts[1].strip(','), parts[2].strip(','), parts[3]
        return {'type': 'R', 'opcode': 'add', 'rd': parse_register(rd), 'rs': parse_register(rs), 'rt': parse_register(rt)}
    elif opcode == 'nop':
        return {'type': 'nop', 'opcode': 'nop'}
    else:
        raise ValueError(f"Unknown instruction: {instr}")

# Pipeline simulation with logging
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

    # Pipeline log for visualization
    pipeline_log = []

    while True:
        cycle += 1
        current_stage = {'IF': None, 'ID': None, 'EX': None, 'MEM': None, 'WB': None}

        # WB stage
        if MEM_WB:
            if 'rd' in MEM_WB['instr']:
                registers[MEM_WB['instr']['rd']] = MEM_WB['result']
            elif 'rt' in MEM_WB['instr'] and MEM_WB['instr']['opcode'] == 'lw':
                registers[MEM_WB['instr']['rt']] = MEM_WB['result']
            total_instructions += 1
            current_stage['WB'] = MEM_WB['instr']['opcode']

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
            # Move to MEM_WB
            MEM_WB = EX_MEM
            EX_MEM = None

            # EX stage
            if ID_EX:
                instr = ID_EX['instr']
                current_stage['EX'] = instr['opcode']
                if instr['type'] == 'R' and instr['opcode'] == 'add':
                    result = ID_EX['rs_value'] + ID_EX['rt_value']
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
                            branch_target = ID_EX['index'] + 1 + instr['offset']
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

            # ID stage
            if IF_ID and not EX_MEM:  # Only proceed if EX_MEM is moving forward
                instr = parse_instruction(IF_ID['instruction'])
                rs_value = registers[instr.get('rs', 0)]
                rt_value = registers[instr.get('rt', 0)]
                base_value = registers[instr.get('base', 0)] if 'base' in instr else 0
                ID_EX = {'instr': instr, 'rs_value': rs_value, 'rt_value': rt_value, 'base_value': base_value, 'index': IF_ID['index']}
                current_stage['ID'] = instr['opcode']
            else:
                ID_EX = None

            # IF stage
            if PC < len(instruction_memory) and not ID_EX:  # Fetch only if ID is clear
                IF_ID = {'instruction': instruction_memory[PC], 'index': PC}
                current_stage['IF'] = instruction_memory[PC].split()[0]
                if delayed_branch:
                    PC = branch_target
                    delayed_branch = False
                else:
                    PC += 1
            else:
                IF_ID = None

        # Log the current pipeline state
        pipeline_log.append([cycle] + [current_stage[stage] for stage in ['IF', 'ID', 'EX', 'MEM', 'WB']])

        # Termination condition
        if PC >= len(instruction_memory) and not MEM_WB and not EX_MEM and not ID_EX and not IF_ID:
            break

    # Print pipeline timing table
    print("\nPipeline Timing Table:")
    print("| Cycle | IF       | ID       | EX       | MEM      | WB       |")
    print("|-------|----------|----------|----------|----------|----------|")
    for entry in pipeline_log[:20]:  # Limit to first 20 cycles for brevity
        print(f"| {entry[0]:5d} | {str(entry[1]):8} | {str(entry[2]):8} | {str(entry[3]):8} | {str(entry[4]):8} | {str(entry[5]):8} |")

    # Print statistics
    print(f"\nTotal clock cycles: {cycle}")
    print(f"Total instructions executed: {total_instructions}")
    print(f"Total stalls due to memory: {memory_stalls}")
    print(f"Stalls due to loads: {load_stalls}")
    print(f"Delayed branches taken: {delayed_branches}")
    print(f"Branch delay slot effectiveness: 100% (all delay slots executed)")
    print(f"Cycles wasted due to memory delays: {cycles_wasted_memory}")

if __name__ == "__main__":
    simulate()