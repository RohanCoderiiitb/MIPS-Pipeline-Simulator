import random

# Simulated memory and registers
data_memory = {i: i // 4 for i in range(0, 44, 4)}  # Memory with initial values 0 to 10 at addresses 0..40
registers = [0] * 32  # 32 registers initialized to 0

# Hardcoded MIPS instruction sequence
instruction_memory = [
    "addi $t0, $zero, 0",      # 0: t0 = 0 (loop counter)
    "addi $s0, $zero, 0",      # 1: s0 = 0 (sum)
    "addi $t3, $zero, 0",      # 2: t3 = 0 (memory pointer)
    "slti $t1, $t0, 10",       # 3: t1 = 1 if t0 < 10, else 0
    "beq $t1, $zero, 5",       # 4: if t1 == 0, branch to index 10
    "lw $t2, 0($t3)",          # 5: load array[t3] into t2
    "add $s0, $s0, $t2",       # 6: s0 += t2
    "addi $t0, $t0, 1",        # 7: t0++
    "addi $t3, $t3, 4",        # 8: t3 += 4 (next element)
    "j 3",                     # 9: jump to index 3
    "sw $s0, 40($zero)",       # 10: store sum at memory[40]
]

# Register name to number mapping
def parse_register(reg):
    reg_map = {'$zero': 0, '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11, '$s0': 16}
    return reg_map.get(reg, 0)

# Parse a single instruction string into a dict
def parse_instruction(instr):
    parts = instr.split()
    opc = parts[0]
    if opc in ('addi', 'slti'):
        rd, rs, imm = parts[1].strip(','), parts[2].strip(','), int(parts[3])
        return {'type':'I','opcode':opc,'dest':parse_register(rd),'rs':parse_register(rs),'imm':imm}
    if opc == 'beq':
        rs, rt, off = parts[1].strip(','), parts[2].strip(','), int(parts[3])
        return {'type':'I','opcode':'beq','rs':parse_register(rs),'rt':parse_register(rt),'offset':off}
    if opc == 'j':
        tgt = int(parts[1])
        return {'type':'J','opcode':'j','target':tgt}
    if opc in ('lw','sw'):
        rt, offbase = parts[1].strip(','), parts[2]
        off, base = offbase.split('(')
        base = base.strip(')')
        return {'type':'I','opcode':opc,'rs':parse_register(base),'rt':parse_register(rt),'offset':int(off)}
    if opc == 'add':
        rd, rs, rt = parts[1].strip(','), parts[2].strip(','), parts[3]
        return {'type':'R','opcode':'add','dest':parse_register(rd),'rs':parse_register(rs),'rt':parse_register(rt)}
    if opc == 'nop':
        return {'type':'nop','opcode':'nop'}
    raise ValueError(f"Unknown instr {instr}")

# Extract source registers for RAW hazard detection
def sources_of(instr):
    if instr['opcode'] in ('add',): return [instr['rs'], instr['rt']]
    if instr['opcode'] in ('addi','slti','lw'): return [instr['rs']]
    if instr['opcode']=='sw': return [instr['rs'], instr['rt']]
    if instr['opcode']=='beq': return [instr['rs'], instr['rt']]
    return []

# Destination register (if any)
def dest_of(instr):
    if instr['opcode'] in ('add','addi','slti'): return instr['dest']
    if instr['opcode']=='lw': return instr['rt']
    return None

# Main pipeline simulation
def simulate():
    PC = 0
    cycle = 0
    pipeline_log = []
    stalls = 0
    load_stalls = 0
    mem_stalls = 0
    cycles_wasted_mem = 0
    total_instr = 0
    branch_delays = 0
    dynamic_nops = 0

    # Pipeline registers
    IF_ID = None
    ID_EX = None
    EX_MEM = None
    MEM_WB = None
    # Branch handling
    branch_pending = False
    branch_target = 0
    nop_for_branch = False

    while True:
        cycle += 1
        stages = {'IF':None,'ID':None,'EX':None,'MEM':None,'WB':None}

        # WB stage
        if MEM_WB:
            stages['WB'] = MEM_WB['instr']['opcode']
            d = dest_of(MEM_WB['instr'])
            if d is not None:
                registers[d] = MEM_WB['result']
            total_instr += 1

        # MEM stage
        stall_mem = False
        if EX_MEM and EX_MEM['cycles'] > 1:
            EX_MEM['cycles'] -= 1
            mem_stalls += 1
            cycles_wasted_mem += 1
            stall_mem = True
            stages['MEM'] = f"{EX_MEM['instr']['opcode']}({EX_MEM['cycles']})"
        else:
            stages['MEM'] = EX_MEM['instr']['opcode'] if EX_MEM else None

        # Only advance if not stalled in MEM
        if not stall_mem:
            MEM_WB = EX_MEM
            EX_MEM = None

            # EX stage
            if ID_EX:
                instr = ID_EX['instr']
                stages['EX'] = instr['opcode']
                # ALU & memory logic unchanged...
                # (omitted for brevity)

            # ID stage
            if IF_ID:
                inst = parse_instruction(IF_ID['instr'])
                srcs = sources_of(inst)
                # RAW via ID_EX dest
                d1 = ID_EX['instr']['dest'] if ID_EX and 'dest' in ID_EX['instr'] else None
                if d1 in srcs:
                    hazard = True
                # load-use hazard via EX_MEM
                d2 = dest_of(EX_MEM['instr']) if EX_MEM else None
                if EX_MEM and EX_MEM['instr']['opcode']=='lw' and d2 in srcs:
                    hazard = True
                    load_stalls += 1
                if hazard:
                    stalls += 1
                    stages['ID'] = 'nop'
                    ID_EX = {'instr':{'opcode':'nop'}, 'rs_val':0, 'rt_val':0, 'idx':-1}
                else:
                    # **Fixed: direct index into registers list**
                    rs_val = registers[inst['rs']] if 'rs' in inst else 0
                    rt_val = registers[inst['rt']] if 'rt' in inst else 0
                    ID_EX = {
                        'instr': inst,
                        'rs_val': rs_val,
                        'rt_val': rt_val,
                        'idx': IF_ID['idx']
                    }
                    stages['ID'] = inst['opcode']
                    if inst['opcode'] in ('beq','j'):
                        nop_for_branch = True
                        dynamic_nops += 1
            else:
                ID_EX = None

            # IF stage
            if PC < len(instruction_memory):
                if nop_for_branch:
                    IF_ID = {'instr':'nop','idx':-1}
                    stages['IF'] = 'nop'
                    nop_for_branch = False
                else:
                    if branch_pending:
                        PC = branch_target
                        branch_pending = False
                    IF_ID = {'instr':instruction_memory[PC],'idx':PC}
                    stages['IF'] = instruction_memory[PC].split()[0]
                    PC += 1
            else:
                IF_ID = None

        pipeline_log.append([cycle, stages['IF'], stages['ID'], stages['EX'], stages['MEM'], stages['WB']])
        if PC >= len(instruction_memory) and not any((IF_ID, ID_EX, EX_MEM, MEM_WB)):
            break

    # Print pipeline table
    print("| Cycle | IF | ID | EX | MEM | WB |")
    print("|-------|----|----|----|-----|----|")
    for c, if_, id_, ex, mem, wb in pipeline_log:
        print(f"| {c:5d} | {if_ or '':4} | {id_ or '':4} | {ex or '':4} | {mem or '':5} | {wb or '':4} |")

    # Statistics
    print(f"Total cycles: {cycle}")
    print(f"Total instr: {total_instr}")
    print(f"Total stalls: {stalls}")
    print(f"Load-use stalls: {load_stalls}")
    print(f"Mem stalls cycles: {mem_stalls}")
    print(f"Cycles wasted to mem: {cycles_wasted_mem}")
    print(f"Branch delay slots: {branch_delays}, NOPs inserted: {dynamic_nops}")

if __name__=='__main__':
    simulate()
