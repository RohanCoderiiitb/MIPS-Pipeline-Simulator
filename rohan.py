import random

# Simulated memory and registers
memory = {i: i // 4 for i in range(0, 40, 4)}  # Memory with initial values 0 to 9 at addresses 0 to 36
registers = [0] * 32  # 32 registers initialized to 0

# Instruction memory: Array sum with a loop (NOPs removed)
instruction_memory = [
    "addi $t0, $zero, 0",      # 0: t0 = 0 (loop counter)
    "addi $s0, $zero, 0",      # 1: s0 = 0 (sum)
    "addi $t3, $zero, 0",      # 2: t3 = 0 (memory pointer)
    "slti $t1, $t0, 10",       # 3: t1 = 1 if t0 < 10, else 0
    "beq $t1, $zero, 7",       # 4: if t1 == 0, branch to endloop (offset = 7)
    # NOP will be inserted dynamically
    "lw $t2, 0($t3)",          # 5: load array[t3] into t2
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

# Check for data hazards
def check_data_hazard(current_instr, previous_instr):
    if not previous_instr or not current_instr:
        return False
        
    # Check for load hazard
    if previous_instr['opcode'] == 'lw':
        dest_reg = previous_instr['rt']
        # Check if current instruction uses the destination of previous load
        if 'rs' in current_instr and current_instr['rs'] == dest_reg:
            return True
        if 'rt' in current_instr and current_instr['rt'] == dest_reg:
            return True
    
    return False

# Pipeline simulation with dynamic NOP insertion and hazard handling
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
    nop_inserted = False  # Flag to ensure we only insert one NOP
    
    # For load hazard detection
    load_hazard = False

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

        # MEM stage processing
        mem_stalled = False
        next_MEM_WB = None
        
        if EX_MEM:
            current_stage['MEM'] = EX_MEM['instr']['opcode']
            
            if EX_MEM['cycles_left'] > 1:
                # Memory operation in progress
                EX_MEM['cycles_left'] -= 1
                memory_stalls += 1
                cycles_wasted_memory += 1
                if EX_MEM['instr']['opcode'] == 'lw':
                    load_stalls += 1
                mem_stalled = True
                current_stage['MEM'] = f"{EX_MEM['instr']['opcode']} ({EX_MEM['cycles_left']})"
            else:
                # Memory operation complete, move to WB
                next_MEM_WB = EX_MEM
        
        # Move completed memory operations to WB
        if next_MEM_WB:
            MEM_WB = next_MEM_WB
            EX_MEM = None
        else:
            MEM_WB = None

        # Only update rest of pipeline if not stalled
        next_EX_MEM = None
        next_ID_EX = None
        next_IF_ID = None
        
        # EX stage
        if ID_EX and not mem_stalled:
            instr = ID_EX['instr']
            current_stage['EX'] = instr['opcode']
            
            if instr['type'] == 'R' and instr['opcode'] == 'add':
                result = ID_EX['rs_value'] + ID_EX['rt_value']
                next_EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
            elif instr['type'] == 'I':
                if instr['opcode'] == 'addi':
                    result = ID_EX['rs_value'] + instr['imm']
                    next_EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                elif instr['opcode'] == 'slti':
                    result = 1 if ID_EX['rs_value'] < instr['imm'] else 0
                    next_EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                elif instr['opcode'] == 'beq':
                    if ID_EX['rs_value'] == ID_EX['rt_value']:
                        delayed_branch = True
                        branch_target = ID_EX['index'] + 1 + instr['offset']
                        delayed_branches += 1
                    next_EX_MEM = {'instr': instr, 'cycles_left': 1}
                elif instr['opcode'] == 'lw':
                    address = ID_EX['base_value'] + instr['offset']
                    result = memory.get(address, 0)
                    next_EX_MEM = {'instr': instr, 'cycles_left': 2, 'result': result}  # 2 cycles for lw
                elif instr['opcode'] == 'sw':
                    address = ID_EX['base_value'] + instr['offset']
                    memory[address] = ID_EX['rt_value']
                    next_EX_MEM = {'instr': instr, 'cycles_left': 3}  # 3 cycles for sw
            elif instr['type'] == 'J' and instr['opcode'] == 'j':
                delayed_branch = True
                branch_target = instr['target']
                delayed_branches += 1
                next_EX_MEM = {'instr': instr, 'cycles_left': 1}
            elif instr['type'] == 'nop':
                next_EX_MEM = {'instr': instr, 'cycles_left': 1}
        
        # ID stage - Check for hazards
        if IF_ID and not mem_stalled:
            instr = parse_instruction(IF_ID['instruction'])
            current_stage['ID'] = instr['opcode']
            
            # Check for load-use hazard between ID_EX and IF_ID
            if ID_EX and ID_EX['instr']['opcode'] == 'lw':
                if check_data_hazard(instr, ID_EX['instr']):
                    # Load hazard detected, stall the pipeline by inserting a bubble
                    load_hazard = True
                    load_stalls += 1
                    current_stage['ID'] = f"{instr['opcode']} (stalled)"
                else:
                    # No hazard, proceed normally
                    rs_value = registers[instr.get('rs', 0)]
                    rt_value = registers[instr.get('rt', 0)]
                    base_value = registers[instr.get('base', 0)] if 'base' in instr else 0
                    next_ID_EX = {'instr': instr, 'rs_value': rs_value, 'rt_value': rt_value, 
                                  'base_value': base_value, 'index': IF_ID['index']}
                    
                    # Detect branch instructions to set up NOP insertion
                    if instr['opcode'] in ['beq', 'j']:
                        insert_nop = True
                        nop_inserted = False
            else:
                # No load in EX stage, proceed normally
                rs_value = registers[instr.get('rs', 0)]
                rt_value = registers[instr.get('rt', 0)]
                base_value = registers[instr.get('base', 0)] if 'base' in instr else 0
                next_ID_EX = {'instr': instr, 'rs_value': rs_value, 'rt_value': rt_value,
                              'base_value': base_value, 'index': IF_ID['index']}
                
                # Detect branch instructions
                if instr['opcode'] in ['beq', 'j']:
                    insert_nop = True
                    nop_inserted = False
        
        # IF stage: Fetch every cycle unless stalled
        if PC < len(instruction_memory) and not mem_stalled and not load_hazard:
            # Check if we need to insert a NOP
            if insert_nop and not nop_inserted:
                next_IF_ID = {'instruction': "nop", 'index': -1}  # Dynamic NOP
                current_stage['IF'] = "nop"
                nop_inserted = True
                dynamic_nops_inserted += 1
            else:
                next_IF_ID = {'instruction': instruction_memory[PC], 'index': PC}
                current_stage['IF'] = instruction_memory[PC].split()[0]
                if delayed_branch:
                    PC = branch_target
                    delayed_branch = False
                else:
                    PC += 1
                # Reset NOP insertion flags
                if nop_inserted:
                    insert_nop = False
                    nop_inserted = False
        
        # Update pipeline registers
        if not mem_stalled:
            if next_EX_MEM:
                EX_MEM = next_EX_MEM
            
            if not load_hazard:
                if next_ID_EX:
                    ID_EX = next_ID_EX
                else:
                    ID_EX = None
                
                if next_IF_ID:
                    IF_ID = next_IF_ID
                else:
                    IF_ID = None
            else:
                # If load hazard, only update IF-ID and ID-EX once the hazard is resolved
                # The pipeline is now stalled until the load completes
                pass
        
        # Reset load hazard flag for next cycle
        load_hazard = False

        # Log the current pipeline state
        pipeline_log.append([cycle] + [current_stage[stage] for stage in ['IF', 'ID', 'EX', 'MEM', 'WB']])

        # Termination condition - all instructions completed and pipeline empty
        if PC >= len(instruction_memory) and not MEM_WB and not EX_MEM and not ID_EX and not IF_ID:
            break

    # Print pipeline timing table
    print("\nPipeline Timing Table:")
    print("| Cycle | IF       | ID       | EX       | MEM      | WB       |")
    print("|-------|----------|----------|----------|----------|----------|")
    for entry in pipeline_log[:25]:  # Show a few more cycles to see hazard handling
        print(f"| {entry[0]:5d} | {str(entry[1]):8} | {str(entry[2]):8} | {str(entry[3]):8} | {str(entry[4]):8} | {str(entry[5]):8} |")

    # Print statistics
    print(f"\nTotal clock cycles: {cycle}")
    print(f"Total instructions executed: {total_instructions}")
    print(f"Total stalls due to memory: {memory_stalls}")
    print(f"Stalls due to loads: {load_stalls}")
    print(f"Delayed branches taken: {delayed_branches}")
    print(f"Dynamic NOPs inserted: {dynamic_nops_inserted}")
    print(f"Branch delay slot effectiveness: 100% (all delay slots used for NOPs)")
    print(f"Cycles wasted due to memory delays: {cycles_wasted_memory}")
    print(f"\nRegister $s0 final value (sum): {registers[16]}")
    print(f"Memory[40] final value: {memory.get(40, 'Not written')}")

if __name__ == "__main__":
    simulate()