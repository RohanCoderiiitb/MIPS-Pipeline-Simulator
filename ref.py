import random

# Simulated memory and registers
memory = {i: i // 4 for i in range(0, 40, 4)}  # Memory with initial values 0 to 9 at addresses 0 to 36
registers = [0] * 32  # 32 registers initialized to 0

# Instruction memory
instruction_memory = [
    "addi $t0, $zero, 5",
    "addi $t1, $zero, 10",
    "add  $t2, $t0, $t1",
    "lw   $t3, 0($t2)",
    "sw   $t3, 4($t2)",
    "slti $t4, $t3, 20",
    "beq  $t4, $zero, 2",
    "add  $s0, $t0, $t4",
    "lw   $s1, 8($t2)",
    "sw   $s1, 12($t2)",
    "addi $s2, $s1, 3",
    "add  $s3, $s2, $s0",
    "slti $s4, $s3, 15",
    "beq  $s4, $zero, 1"
]

# Register mapping
def parse_register(reg):
    reg_map = {
        '$zero': 0, '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11, '$s0': 16,
        '$t4': 12, '$t5': 13, '$t6': 14, '$t7': 15, '$s1': 17, '$s2': 18,
        '$s3': 19, '$s4': 20, '$a0': 4, '$a1': 5, '$a2': 6, '$a3': 7,
        '$v0': 2
    }
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
        return {'type': 'I', 'opcode': opcode, 'rt': parse_register(rt), 'base': parse_register(base), 'offset': int(offset)}
    elif opcode == 'add':
        rd, rs, rt = parts[1].strip(','), parts[2].strip(','), parts[3]
        return {'type': 'R', 'opcode': 'add', 'rd': parse_register(rd), 'rs': parse_register(rs), 'rt': parse_register(rt)}
    elif opcode == 'nop':
        return {'type': 'nop', 'opcode': 'nop'}
    else:
        raise ValueError(f"Unknown instruction: {instr}")

# Simulation function
def simulate():
    PC = 0
    cycle = 0
    total_instructions = 0
    memory_stalls = 0
    delayed_branches = 0
    load_stalls = 0
    cycles_wasted_memory = 0
    dynamic_nops_inserted = 0

    IF_ID = None
    ID_EX = None
    EX_MEM = None
    MEM_WB = None
    delayed_branch = False
    branch_target = 0
    insert_nop = False  # Flag to insert NOP after branch

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
                        EX_MEM = {'instr': instr, 'cycles_left': 2}
                elif instr['type'] == 'J' and instr['opcode'] == 'j':
                    delayed_branch = True
                    branch_target = instr['target']
                    delayed_branches += 1
                    EX_MEM = {'instr': instr, 'cycles_left': 1}
                elif instr['type'] == 'nop':
                    EX_MEM = {'instr': instr, 'cycles_left': 1}

            # ID stage
            if IF_ID:
                instr = parse_instruction(IF_ID['instruction'])
                rs_value = registers[instr.get('rs', 0)]
                rt_value = registers[instr.get('rt', 0)]
                base_value = registers[instr.get('base', 0)] if 'base' in instr else 0
                ID_EX = {'instr': instr, 'rs_value': rs_value, 'rt_value': rt_value, 'base_value': base_value, 'index': IF_ID['index']}
                current_stage['ID'] = instr['opcode']
                
                # Detect branch instructions to set NOP insertion flag
                if instr['opcode'] in ['beq', 'j']:
                    insert_nop = True
            else:
                ID_EX = None

            # IF stage
            if PC < len(instruction_memory) and not stall:
                if insert_nop:
                    IF_ID = {'instruction': "nop", 'index': -1}  # Dynamically inserted NOP
                    current_stage['IF'] = "nop"
                    insert_nop = False
                    dynamic_nops_inserted += 1
                else:
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
        if PC >= len(instruction_memory) and not any((MEM_WB, EX_MEM, ID_EX, IF_ID)):
            break

    print("\nPipeline Timing Table:")
    print("| Cycle | IF       | ID       | EX       | MEM      | WB       |")
    print("|-------|----------|----------|----------|----------|----------|")
    for entry in pipeline_log:
        print(f"| {entry[0]:5d} | {str(entry[1]):8} | {str(entry[2]):8} | {str(entry[3]):8} | {str(entry[4]):8} | {str(entry[5]):8} |")

    print(f"\nTotal clock cycles: {cycle}")
    print(f"Total instructions executed: {total_instructions}")
    print(f"Total stalls due to memory: {memory_stalls}")
    print(f"Stalls due to loads: {load_stalls}")
    print(f"Delayed branches taken: {delayed_branches}")
    print(f"Dynamic NOPs inserted: {dynamic_nops_inserted}")
    print(f"Cycles wasted due to memory delays: {cycles_wasted_memory}")

if __name__ == "__main__":
    simulate()