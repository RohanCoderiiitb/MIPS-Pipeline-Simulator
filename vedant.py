import re

# Register mapping
REGISTERS = {
    '$zero': 0, '$at': 1, '$v0': 2, '$v1': 3, '$a0': 4, '$a1': 5, '$a2': 6, '$a3': 7,
    '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11, '$t4': 12, '$t5': 13, '$t6': 14, '$t7': 15,
    '$s0': 16, '$s1': 17, '$s2': 18, '$s3': 19, '$s4': 20, '$s5': 21, '$s6': 22, '$s7': 23,
    '$t8': 24, '$t9': 25, '$k0': 26, '$k1': 27, '$gp': 28, '$sp': 29, '$fp': 30, '$ra': 31
}

# Supported instruction formats
INSTRUCTION_FORMATS = {
    'add': 'R', 'sub': 'R', 'and': 'R', 'or': 'R', 'sll': 'R', 'srl': 'R', 'slt': 'R',
    'addi': 'I', 'andi': 'I', 'ori': 'I', 'lw': 'I', 'sw': 'I', 'beq': 'I', 'bne': 'I',
    'j': 'J', 'jal': 'J', 'jr': 'J', 'li': 'pseudo', 'move': 'pseudo'
}

def parse_asm_file(filename):
    instructions = []
    labels = {}
    address = 0
    with open(filename, 'r') as f:
        for line in f:
            line = line.split('#')[0].strip()  # Remove comments
            if not line:
                continue
            if line.endswith(':'):
                labels[line[:-1]] = address
                continue
            parts = re.split(r'[,\s]+', line)
            op = parts[0]
            instr = {'op': op, 'address': address}
            if op in INSTRUCTION_FORMATS:
                fmt = INSTRUCTION_FORMATS[op]
                if fmt == 'R':
                    if op in ['sll', 'srl']:
                        instr['rd'] = parts[1]
                        instr['rt'] = parts[2]
                        instr['shamt'] = int(parts[3])
                    else:
                        instr['rd'] = parts[1]
                        instr['rs'] = parts[2]
                        instr['rt'] = parts[3]
                elif fmt == 'I':
                    if op in ['lw', 'sw']:
                        match = re.match(r'(-?\d+)\((\$[a-z0-9]+)\)', parts[2])
                        if not match:
                            raise ValueError(f"Invalid format for {op}: {parts[2]}")
                        instr['rt'] = parts[1]
                        instr['imm'] = int(match.group(1))
                        instr['rs'] = match.group(2)
                    elif op in ['beq', 'bne']:
                        instr['rs'] = parts[1]
                        instr['rt'] = parts[2]
                        instr['label'] = parts[3]
                    else:
                        instr['rt'] = parts[1]
                        instr['rs'] = parts[2]
                        instr['imm'] = int(parts[3])
                elif fmt == 'J':
                    if op == 'jr':
                        instr['rs'] = parts[1]
                    else:
                        instr['label'] = parts[1]
                elif fmt == 'pseudo':
                    if op == 'li':
                        instr['rt'] = parts[1]
                        instr['imm'] = int(parts[2])
                    elif op == 'move':
                        instr['rd'] = parts[1]
                        instr['rs'] = parts[2]
            instructions.append(instr)
            address += 4
    # Resolve labels for branches and jumps
    for instr in instructions:
        if 'label' in instr and instr['label'] in labels:
            instr['target'] = labels[instr['label']]
    return instructions

def simulate_pipeline(instructions):
    registers = [0] * 32
    registers[REGISTERS['$sp']] = 1000
    memory = {}
    pc = 0
    clock = 0
    pipeline = {'IF': None, 'ID': None, 'EX': None, 'MEM': None, 'WB': None}
    diagram = []
    metrics = {'cycles':0, 'load_stalls':0, 'mem_delays':0, 'branches':0, 'instructions':0}

    def execute(instr):
        op = instr['op']
        if op == 'add': return registers[REGISTERS[instr['rs']]] + registers[REGISTERS[instr['rt']]]
        if op == 'sub': return registers[REGISTERS[instr['rs']]] - registers[REGISTERS[instr['rt']]]
        if op == 'and': return registers[REGISTERS[instr['rs']]] & registers[REGISTERS[instr['rt']]]
        if op == 'or':  return registers[REGISTERS[instr['rs']]] | registers[REGISTERS[instr['rt']]]
        if op == 'slt': return 1 if registers[REGISTERS[instr['rs']]] < registers[REGISTERS[instr['rt']]] else 0
        if op == 'sll': return registers[REGISTERS[instr['rt']]] << instr['shamt']
        if op == 'srl': return registers[REGISTERS[instr['rt']]] >> instr['shamt']
        if op == 'addi': return registers[REGISTERS[instr['rs']]] + instr['imm']
        if op == 'andi': return registers[REGISTERS[instr['rs']]] & instr['imm']
        if op == 'ori':  return registers[REGISTERS[instr['rs']]] | instr['imm']
        if op == 'lw':   return memory.get(registers[REGISTERS[instr['rs']]] + instr['imm'], 0)
        if op == 'sw':
            addr = registers[REGISTERS[instr['rs']]] + instr['imm']
            memory[addr] = registers[REGISTERS[instr['rt']]]
        if op == 'li':   return instr['imm']
        if op == 'move':return registers[REGISTERS[instr['rs']]]
        return None

    # Pipeline simulation
    while any(pipeline.values()) or pc//4 < len(instructions):
        clock += 1
        metrics['cycles'] += 1
        stall = False
        comment = []
        next_pc = pc + 4
        # WB
        if pipeline['WB']:
            wb = pipeline['WB']; op=wb['op']
            if op not in ['sw','beq','bne','j','jal','jr']:
                dest = REGISTERS.get(wb.get('rd', wb.get('rt')))
                registers[dest] = wb.get('result', registers[dest])
            elif op == 'jal':
                registers[REGISTERS['$ra']] = wb['address'] + 8
            pipeline['WB'] = None
            metrics['instructions'] += 1
        # MEM
        if pipeline['MEM']:
            mem = pipeline['MEM']
            if 'mem_cycles' not in mem and mem['op'] in ['lw','sw']:
                mem['mem_cycles'] = 2; stall = True; metrics['mem_delays'] += 1
            if 'mem_cycles' in mem and mem['mem_cycles']>1:
                mem['mem_cycles'] -= 1; stall = True; metrics['mem_delays'] += 1
            elif 'mem_cycles' in mem:
                mem['mem_cycles'] -= 1
                if mem['op']=='lw': mem['result']=execute(mem)
                pipeline['WB'] = mem; pipeline['MEM'] = None
            comment.append(f"MEM: {mem['op']}")
        # EX
        if pipeline['EX'] and not stall:
            ex = pipeline['EX']
            if ex['op'] not in ['beq','bne','j','jal','jr','sw']:
                ex['result'] = execute(ex)
            if not pipeline['MEM']:
                pipeline['MEM'] = ex; pipeline['EX']=None
            comment.append(f"EX: {ex['op']}")
        # ID
        if pipeline['ID'] and not stall:
            idr = pipeline['ID']; op=idr['op']
            if op in ['beq','bne']:
                metrics['branches']+=1
                taken = (registers[REGISTERS[idr['rs']]] == registers[REGISTERS[idr['rt']]])
                if (op=='beq' and taken) or (op=='bne' and not taken):
                    next_pc = idr['target']; comment.append(f"ID: {op} {'taken' if taken else 'not taken'}")
            if op in ['j','jal']:
                next_pc = idr['target']; comment.append(f"ID: {op}")
            if op=='jr':
                next_pc = registers[REGISTERS[idr['rs']]]; comment.append("ID: jr to address")
            if not pipeline['EX']:
                pipeline['EX']=idr; pipeline['ID']=None
        # IF
        if not stall and pc//4 < len(instructions) and not pipeline['ID']:
            fetch = instructions[pc//4].copy(); fetch['address']=pc
            pipeline['ID']=fetch; comment.append(f"IF: {fetch['op']}"); pc=next_pc
        # Record state
        diagram.append({'cycle':clock,'IF':pipeline['ID']['op'] if pipeline['ID'] else 'NOP',
                        'ID':pipeline['EX']['op'] if pipeline['EX'] else 'NOP',
                        'EX':pipeline['MEM']['op'] if pipeline['MEM'] else 'NOP',
                        'MEM':pipeline['WB']['op'] if pipeline['WB'] else 'NOP',
                        'WB':'NOP','comment':'; '.join(comment) or 'Normal'})
    # Output
    print("\nPipeline Diagram:")
    print(f"{'Cycle':<6} | {'IF':<6} | {'ID':<6} | {'EX':<6} | {'MEM':<6} | {'WB':<6} | Comments")
    print('-'*70)
    for s in diagram:
        print(f"{s['cycle']:<6} | {s['IF']:<6} | {s['ID']:<6} | {s['EX']:<6} | {s['MEM']:<6} | {s['WB']:<6} | {s['comment']}")

    # Metrics & Registers
    print("\nMetrics:")
    print(f"Total Cycles: {metrics['cycles']} | Instructions: {metrics['instructions']} | "
          f"Memory Delays: {metrics['mem_delays']} | Branches: {metrics['branches']}")
    print("\nFinal Registers:")
    for r,idx in REGISTERS.items(): print(f"{r}: {registers[idx]}")

if __name__ == '__main__':
    instrs = parse_asm_file('Binary.asm')
    simulate_pipeline(instrs)
