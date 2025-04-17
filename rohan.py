import re
import time
import random

# Color codes for output
YELLOW = "\033[93m"  # IF stage
PINK = "\033[95m"    # ID stage
CYAN = "\033[96m"    # EX stage
BLUE = "\033[94m"    # MEM stage
GREEN = "\033[92m"   # WB stage
RED = "\033[91m"
RESET = "\033[0m"

registers = {
    '$0': 0, '$at': 1, '$v0': 2, '$v1': 3, '$a0': 4, '$a1': 5, '$a2': 6, '$a3': 7,
    '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11, '$t4': 12, '$t5': 13, '$t6': 14, '$t7': 15,
    '$s0': 16, '$s1': 17, '$s2': 18, '$s3': 19, '$s4': 20, '$s5': 21, '$s6': 22, '$s7': 23,
    '$t8': 24, '$t9': 25, '$k0': 26, '$k1': 27, '$gp': 28, '$sp': 29, '$fp': 30, '$ra': 31
}

def encode_r_type(opcode, rs, rt, rd, shamt, funct):
    return f"{opcode:06b}{rs:05b}{rt:05b}{rd:05b}{shamt:05b}{funct:06b}"

def encode_i_type(opcode, rs, rt, imm):
    imm = imm & 0xFFFF if imm >= 0 else imm & 0xFFFF
    return f"{opcode:06b}{rs:05b}{rt:05b}{imm:016b}"

def encode_j_type(opcode, address):
    return f"{opcode:06b}{address:026b}"

# Parse assembly file
data_labels = {}
text_labels = {}
text_instructions = []
instructions = []
memory = {}

with open('BinarySearch.asm', 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f.readlines()]

in_data = False
in_text = False
data_address = 0x10010000
text_address = 0x00400000

for line in lines:
    line = line.split('#')[0].strip()
    if not line:
        continue
    if line == '.data':
        in_data = True
        in_text = False
        continue
    elif line == '.text':
        in_data = False
        in_text = True
        continue
    if in_data:
        if ':' in line:
            parts = line.split(':', 1)
            label = parts[0].strip()
            directive = parts[1].strip()
            data_labels[label] = data_address
            if directive.startswith('.asciiz'):
                match = re.search(r'"(.*?)"', directive)
                string = match.group(1)
                for i, char in enumerate(string):
                    memory[data_address + i] = ord(char)
                memory[data_address + len(string)] = 0
                data_address += len(string) + 1
    elif in_text:
        if ':' in line:
            parts = line.split(':', 1)
            label = parts[0].strip()
            text_labels[label] = text_address
            if parts[1].strip():
                text_instructions.append((text_address, parts[1].strip()))
                text_address += 4
        elif line:
            text_instructions.append((text_address, line))
            text_address += 4

# Assemble instructions
current_address = 0x00400000
for addr, line in text_instructions:
    parts = line.replace(',', ' ').split()
    instr = parts[0]
    if instr == 'addi':
        rt, rs, imm = parts[1], parts[2], int(parts[3])
        binary = encode_i_type(0x08, registers[rs], registers[rt], imm)
        instructions.append({'address': current_address, 'type': 'I', 'name': 'addi', 'rs': registers[rs], 'rt': registers[rt], 'imm': imm})
    elif instr == 'srl':
        rd, rt, shamt = parts[1], parts[2], int(parts[3])
        binary = encode_r_type(0, 0, registers[rt], registers[rd], shamt, 0x02)
        instructions.append({'address': current_address, 'type': 'R', 'name': 'srl', 'rs': 0, 'rt': registers[rt], 'rd': registers[rd], 'shamt': shamt, 'funct': 0x02})
    elif instr == 'sll':
        rd, rt, shamt = parts[1], parts[2], int(parts[3])
        binary = encode_r_type(0, 0, registers[rt], registers[rd], shamt, 0x00)
        instructions.append({'address': current_address, 'type': 'R', 'name': 'sll', 'rs': 0, 'rt': registers[rt], 'rd': registers[rd], 'shamt': shamt, 'funct': 0x00})
    elif instr == 'add':
        rd, rs, rt = parts[1], parts[2], parts[3]
        binary = encode_r_type(0, registers[rs], registers[rt], registers[rd], 0, 0x20)
        instructions.append({'address': current_address, 'type': 'R', 'name': 'add', 'rs': registers[rs], 'rt': registers[rt], 'rd': registers[rd], 'funct': 0x20})
    elif instr == 'sub':
        rd, rs, rt = parts[1], parts[2], parts[3]
        binary = encode_r_type(0, registers[rs], registers[rt], registers[rd], 0, 0x22)
        instructions.append({'address': current_address, 'type': 'R', 'name': 'sub', 'rs': registers[rs], 'rt': registers[rt], 'rd': registers[rd], 'funct': 0x22})
    elif instr == 'slt':
        rd, rs, rt = parts[1], parts[2], parts[3]
        binary = encode_r_type(0, registers[rs], registers[rt], registers[rd], 0, 0x2A)
        instructions.append({'address': current_address, 'type': 'R', 'name': 'slt', 'rs': registers[rs], 'rt': registers[rt], 'rd': registers[rd], 'funct': 0x2A})
    elif instr == 'beq':
        rs, rt, label = parts[1], parts[2], parts[3]
        offset = (text_labels[label] - (current_address + 4)) // 4
        binary = encode_i_type(0x04, registers[rs], registers[rt], offset)
        instructions.append({'address': current_address, 'type': 'I', 'name': 'beq', 'rs': registers[rs], 'rt': registers[rt], 'imm': offset})
    elif instr == 'bne':
        rs, rt, label = parts[1], parts[2], parts[3]
        offset = (text_labels[label] - (current_address + 4)) // 4
        binary = encode_i_type(0x05, registers[rs], registers[rt], offset)
        instructions.append({'address': current_address, 'type': 'I', 'name': 'bne', 'rs': registers[rs], 'rt': registers[rt], 'imm': offset})
    elif instr == 'lw':
        rt, offset_rs = parts[1], parts[2]
        offset, rs = int(offset_rs.split('(')[0]), registers[offset_rs.split('(')[1][:-1]]
        binary = encode_i_type(0x23, rs, registers[rt], offset)
        instructions.append({'address': current_address, 'type': 'I', 'name': 'lw', 'rs': rs, 'rt': registers[rt], 'imm': offset})
    elif instr == 'sw':
        rt, offset_rs = parts[1], parts[2]
        offset, rs = int(offset_rs.split('(')[0]), registers[offset_rs.split('(')[1][:-1]]
        binary = encode_i_type(0x2B, rs, registers[rt], offset)
        instructions.append({'address': current_address, 'type': 'I', 'name': 'sw', 'rs': rs, 'rt': registers[rt], 'imm': offset})
    elif instr == 'jal':
        label = parts[1]
        target = text_labels[label]
        address = (target >> 2) & 0x3FFFFFF
        binary = encode_j_type(0x03, address)
        instructions.append({'address': current_address, 'type': 'J', 'name': 'jal', 'target_address': target})
    elif instr == 'j':
        label = parts[1]
        target = text_labels[label]
        address = (target >> 2) & 0x3FFFFFF
        binary = encode_j_type(0x02, address)
        instructions.append({'address': current_address, 'type': 'J', 'name': 'j', 'target_address': target})
    elif instr == 'jr':
        rs = parts[1]
        binary = encode_r_type(0, registers[rs], 0, 0, 0, 0x08)
        instructions.append({'address': current_address, 'type': 'R', 'name': 'jr', 'rs': registers[rs], 'funct': 0x08})
    elif instr == 'li':
        reg, imm = parts[1], int(parts[2])
        binary = encode_i_type(0x08, 0, registers[reg], imm)
        instructions.append({'address': current_address, 'type': 'I', 'name': 'addi', 'rs': 0, 'rt': registers[reg], 'imm': imm})
    elif instr == 'la':
        reg, label = parts[1], parts[2]
        addr = data_labels[label]
        hi, lo = (addr >> 16) & 0xFFFF, addr & 0xFFFF
        instructions.append({'address': current_address, 'type': 'I', 'name': 'lui', 'rt': 1, 'imm': hi})
        current_address += 4
        binary = encode_i_type(0x0D, 1, registers[reg], lo)
        instructions.append({'address': current_address, 'type': 'I', 'name': 'ori', 'rs': 1, 'rt': registers[reg], 'imm': lo})
    elif instr == 'syscall':
        binary = '00000000000000000000000000001100'
        instructions.append({'address': current_address, 'type': 'syscall', 'name': 'syscall'})
    current_address += 4

# Simulate pipeline
def simulate(instructions):
    PC = 0x00400000
    cycle = 0
    IF_ID = ID_EX = EX_MEM = MEM_WB = None
    branch_delay = False
    branch_target = None
    mem_cycles_left = 0
    regs = [0] * 32
    global memory

    total_cycles = total_stalls = instructions_executed = load_stalls = branch_slots_useful = mem_delay_cycles = 0

    print(f"{'Cycle':^7}|{YELLOW}{'IF':^10}{RESET}|{PINK}{'ID':^10}{RESET}|{CYAN}{'EX':^10}{RESET}|{BLUE}{'MEM':^10}{RESET}|{GREEN}{'WB':^10}{RESET}|")
    print("-" * 61)

    while True:
        cycle += 1
        total_cycles += 1

        # WB Stage
        if MEM_WB:
            instr = MEM_WB['instr']
            instructions_executed += 1
            if instr['type'] == 'R' and 'rd' in instr and instr['rd'] != 0 and 'result' in MEM_WB:
                regs[instr['rd']] = MEM_WB['result']
            elif instr['type'] == 'I' and 'rt' in instr and instr['rt'] != 0 and 'result' in MEM_WB:
                regs[instr['rt']] = MEM_WB['result']
            elif instr['name'] == 'jal':
                regs[31] = MEM_WB['result']
            elif instr['name'] == 'syscall':
                if regs[2] == 4:
                    addr = regs[4]
                    string = ""
                    while memory.get(addr, 0) != 0:
                        string += chr(memory[addr])
                        addr += 1
                    print(string, end="")
                elif regs[2] == 5:
                    regs[2] = int(input())
                elif regs[2] == 1:
                    print(regs[4], end="")
                elif regs[2] == 10:
                    print("\nProgram exited.")
                    break

        # MEM Stage
        stall = False
        if EX_MEM:
            instr = EX_MEM['instr']
            if instr['name'] in ['lw', 'sw']:
                if mem_cycles_left == 0:
                    cycles = random.choice([2, 3])
                    mem_cycles_left = cycles - 1
                    mem_delay_cycles += cycles
                    if instr['name'] == 'lw':
                        load_stalls += cycles
                elif mem_cycles_left > 0:
                    mem_cycles_left -= 1
                    stall = True
                if not stall:
                    if instr['name'] == 'lw':
                        addr = EX_MEM['result']
                        MEM_WB = {'instr': instr, 'result': memory.get(addr, 0)}
                    elif instr['name'] == 'sw':
                        memory[EX_MEM['result']] = regs[instr['rt']]
                        MEM_WB = {'instr': instr}
            else:
                MEM_WB = EX_MEM
        else:
            MEM_WB = None

        # EX Stage
        if ID_EX and not stall:
            instr = ID_EX['instr']
            if instr['type'] == 'R':
                rs_val = regs[instr['rs']] if 'rs' in instr else 0
                rt_val = regs[instr['rt']] if 'rt' in instr else 0
                if instr['name'] == 'add':
                    EX_MEM = {'instr': instr, 'result': rs_val + rt_val}
                elif instr['name'] == 'sub':
                    EX_MEM = {'instr': instr, 'result': rs_val - rt_val}
                elif instr['name'] == 'slt':
                    EX_MEM = {'instr': instr, 'result': 1 if rs_val < rt_val else 0}
                elif instr['name'] == 'srl':
                    EX_MEM = {'instr': instr, 'result': rt_val >> instr['shamt']}
                elif instr['name'] == 'sll':
                    EX_MEM = {'instr': instr, 'result': rt_val << instr['shamt']}
                elif instr['name'] == 'jr':
                    branch_target = rs_val
                    branch_delay = True
                    branch_slots_useful += 1
                    EX_MEM = None
            elif instr['type'] == 'I':
                rs_val = regs[instr['rs']] if 'rs' in instr else 0
                if instr['name'] == 'addi':
                    EX_MEM = {'instr': instr, 'result': rs_val + instr['imm']}
                elif instr['name'] == 'lw' or instr['name'] == 'sw':
                    EX_MEM = {'instr': instr, 'result': rs_val + instr['imm']}
                elif instr['name'] == 'beq':
                    if regs[instr['rs']] == regs[instr['rt']]:
                        branch_target = ID_EX['pc'] + 4 + (instr['imm'] << 2)
                        branch_delay = True
                        branch_slots_useful += 1
                    EX_MEM = {'instr': instr}
                elif instr['name'] == 'bne':
                    if regs[instr['rs']] != regs[instr['rt']]:
                        branch_target = ID_EX['pc'] + 4 + (instr['imm'] << 2)
                        branch_delay = True
                        branch_slots_useful += 1
                    EX_MEM = {'instr': instr}
            elif instr['type'] == 'J':
                branch_target = instr['target_address']
                branch_delay = True
                branch_slots_useful += 1
                EX_MEM = {'instr': instr, 'result': ID_EX['pc'] + 8} if instr['name'] == 'jal' else {'instr': instr}
            elif instr['type'] == 'syscall':
                EX_MEM = {'instr': instr}
        else:
            EX_MEM = None

        # ID Stage
        if IF_ID and not stall:
            instr = IF_ID['instr']
            ID_EX = {'instr': instr, 'pc': IF_ID['pc']}
        else:
            ID_EX = None

        # IF Stage
        if not stall:
            if branch_delay:
                delay_slot_addr = PC
                PC = branch_target
                branch_delay = False
                instr_index = (delay_slot_addr - 0x00400000) // 4
                IF_ID = {'instr': instructions[instr_index], 'pc': delay_slot_addr} if 0 <= instr_index < len(instructions) else None
            else:
                instr_index = (PC - 0x00400000) // 4
                if 0 <= instr_index < len(instructions):
                    IF_ID = {'instr': instructions[instr_index], 'pc': PC}
                    PC += 4
                else:
                    IF_ID = None
        else:
            total_stalls += 1
            IF_ID = None

        # Visualize
        stages = [
            IF_ID['instr']['name'] if IF_ID else '',
            ID_EX['instr']['name'] if ID_EX else '',
            EX_MEM['instr']['name'] if EX_MEM else '',
            MEM_WB['instr']['name'] + f'({mem_cycles_left})' if MEM_WB and mem_cycles_left > 0 else (MEM_WB['instr']['name'] if MEM_WB else ''),
            MEM_WB['instr']['name'] if MEM_WB else ''
        ]
        colors = [YELLOW, PINK, CYAN, BLUE, GREEN]
        print(f"{cycle:^7}|", end='')
        for i, stage in enumerate(stages):
            print(f"{colors[i]}{stage:^10}{RESET}|", end='')
        print()
        time.sleep(0.1)

        if PC >= 0x00400000 + len(instructions) * 4 and not IF_ID and not ID_EX and not EX_MEM and not MEM_WB:
            break

    print(f"\n{YELLOW}Simulation Statistics:{RESET}")
    print(f"Total Clock Cycles: {total_cycles}")
    print(f"Total Stalls: {total_stalls}")
    print(f"Instructions Executed: {instructions_executed}")
    print(f"Stalls due to Loads: {load_stalls}")
    print(f"Branch Delay Slot Effectiveness: {branch_slots_useful} useful slots")
    print(f"Cycles Wasted due to Memory Delays: {mem_delay_cycles}")

simulate(instructions)