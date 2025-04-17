import re

YELLOW = "\033[93m"
PINK = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"

registers = {
    '$0': 0, '$at': 1, '$v0': 2, '$v1': 3, '$a0': 4, '$a1': 5, '$a2': 6, '$a3': 7,
    '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11, '$t4': 12, '$t5': 13, '$t6': 14, '$t7': 15,
    '$s0': 16, '$s1': 17, '$s2': 18, '$s3': 19, '$s4': 20, '$s5': 21, '$s6': 22, '$s7': 23,
    '$t8': 24, '$t9': 25, '$k0': 26, '$k1': 27, '$gp': 28, '$sp': 29, '$fp': 30, '$ra': 31
}

def get_instruction_expansion(instr):
    if instr in ['ble', 'la']:
        return 2
    return 1

def encode_r_type(opcode, rs, rt, rd, shamt, funct):
    return f"{opcode:06b}{rs:05b}{rt:05b}{rd:05b}{shamt:05b}{funct:06b}"

def encode_i_type(opcode, rs, rt, imm):
    imm = imm & 0xFFFF
    return f"{opcode:06b}{rs:05b}{rt:05b}{imm:016b}"

def encode_j_type(opcode, address):
    return f"{opcode:06b}{address:026b}"

def get_data_size(directive_line):
    parts = directive_line.split()
    dir_type = parts[0]
    
    if dir_type == '.asciiz':
        match = re.search(r'"(.*?)"', directive_line)
        if match:
            str_len = len(match.group(1))
            return str_len  if dir_type == '.asciiz' else str_len  
        else:
            raise ValueError("Invalid string directive")
    else:
        raise ValueError(f"Unknown data directive: {dir_type}")

data_labels = {}
text_labels = {}    
text_instructions = []

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
            directive_line = parts[1].strip()
            data_labels[label] = data_address
            size = get_data_size(directive_line)
            data_address += size
        else:
            size = get_data_size(line)
            data_address += size
    elif in_text:
        if ':' in line:
            parts = line.split(':', 1)
            label = parts[0].strip()
            text_labels[label] = text_address
            if parts[1].strip():
                instr = parts[1].strip().split()[0]
                expansion = get_instruction_expansion(instr)
                text_instructions.append((text_address, parts[1].strip()))
                text_address += 4 * expansion
        elif line:
            instr = line.split()[0]
            expansion = get_instruction_expansion(instr)
            text_instructions.append((text_address, line))
            text_address += 4 * expansion

print("\033[93mData labels found:\033[0m")
for label in data_labels:
    print(f"\033[96m{label}\033[0m")

print("\033[93m\nText labels found:\033[0m")
for label in text_labels:
    print(f"\033[96m{label}\033[0m")

print("\033[93m\nText instructions found:\033[0m")
for addr, instr in text_instructions:
    print(f"\033[95m{hex(addr)}\033[0m: \033[96m{instr}\033[0m")

machine_code = []
current_address = 0x00400000

for addr, line in text_instructions:
    parts = line.replace(',', ' ').split()
    instr = parts[0]
    if instr == 'li':
        reg = parts[1]
        imm = int(parts[2])
        binary = encode_i_type(0x09, 0, registers[reg], imm)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'ble':
        rs = parts[1]
        rt = parts[2]
        label = parts[3]
        target_address = text_labels[label]
        binary_slt = encode_r_type(0, registers[rt], registers[rs], 1, 0, 0x2A)
        machine_code.append((current_address, binary_slt))
        current_address += 4
        offset = (target_address - (current_address + 4)) // 4
        binary_beq = encode_i_type(0x04, 1, 0, offset)
        machine_code.append((current_address, binary_beq))
        current_address += 4
    elif instr == 'la':
        reg = parts[1]
        label = parts[2]
        label_address = data_labels[label]
        hi = (label_address >> 16) & 0xFFFF
        lo = label_address & 0xFFFF
        binary_lui = encode_i_type(0x0F, 0, 1, hi)
        machine_code.append((current_address, binary_lui))
        current_address += 4
        binary_ori = encode_i_type(0x0D, 1, registers[reg], lo + 0x1)
        machine_code.append((current_address, binary_ori))
        current_address += 4
    elif instr == 'jal':
        label = parts[1]
        target_address = text_labels[label]
        address = (target_address >> 2) & 0x3FFFFFF
        binary = encode_j_type(0x03, address)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'j':
        label = parts[1]
        target_address = text_labels[label]
        address = (target_address >> 2) & 0x3FFFFFF
        binary = encode_j_type(0x02, address)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'addi':
        rt = parts[1]
        rs = parts[2]
        imm = int(parts[3])
        binary = encode_i_type(0x08, registers[rs], registers[rt], imm)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'or':
        rd = parts[1]
        rs = parts[2]
        rt = parts[3]
        binary = encode_r_type(0, registers[rs], registers[rt], registers[rd], 0, 0x25)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'andi':
        rt = parts[1]
        rs = parts[2]
        imm = int(parts[3])
        binary = encode_i_type(0x0C, registers[rs], registers[rt], imm)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'bne':
        rs = parts[1]
        rt = parts[2]
        label = parts[3]
        target_address = text_labels[label]
        offset = (target_address - (current_address + 4)) // 4
        binary = encode_i_type(0x05, registers[rs], registers[rt], offset)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'srl':
        rd = parts[1]
        rt = parts[2]
        shamt = int(parts[3])
        binary = encode_r_type(0, 0, registers[rt], registers[rd], shamt, 0x02)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'beq':
        rs = parts[1]
        rt = parts[2]
        label = parts[3]
        target_address = text_labels[label]
        offset = (target_address - (current_address + 4)) // 4
        binary = encode_i_type(0x04, registers[rs], registers[rt], offset)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'sub':
        rd = parts[1]
        rs = parts[2]
        rt = parts[3]
        binary = encode_r_type(0, registers[rs], registers[rt], registers[rd], 0, 0x22)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'sllv':
        rd = parts[1]
        rt = parts[2]
        rs = parts[3]
        binary = encode_r_type(0, registers[rs], registers[rt], registers[rd], 0, 0x04)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'syscall':
        binary = '00000000000000000000000000001100'
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'jr':
        rs = parts[1]
        binary = encode_r_type(0, registers[rs], 0, 0, 0, 0x08)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'add':
        rd = parts[1]
        rs = parts[2]
        rt = parts[3]
        binary = encode_r_type(0, registers[rs], registers[rt], registers[rd], 0, 0x20)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'sll':
        rd = parts[1]
        rt = parts[2]
        shamt = int(parts[3])
        binary = encode_r_type(0, 0, registers[rt], registers[rd], shamt, 0x00)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'lw':
        rt = parts[1]
        offset_rs = parts[2]
        offset_str, rs_str = offset_rs.split('(')
        offset = int(offset_str)
        rs = registers[rs_str[:-1]]
        binary = encode_i_type(0x23, rs, registers[rt], offset)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'sw':
        rt = parts[1]
        offset_rs = parts[2]
        offset_str, rs_str = offset_rs.split('(')
        offset = int(offset_str)
        rs = registers[rs_str[:-1]]
        binary = encode_i_type(0x2B, rs, registers[rt], offset)
        machine_code.append((current_address, binary))
        current_address += 4
    elif instr == 'slt':
        rd = parts[1]
        rs = parts[2]
        rt = parts[3]
        binary = encode_r_type(0, registers[rs], registers[rt], registers[rd], 0, 0x2A)
        machine_code.append((current_address, binary))
        current_address += 4
    else:
        print(f"\033[91mUnknown instruction: {instr}\033[0m")
        exit(1)

with open('machine_code.txt', 'w') as f:
    for _, binary in machine_code:
        f.write(binary + '\n')

    print(f"\n{YELLOW}Data label addresses assigned:{RESET}")
    for label, addr in data_labels.items():
        print(f"{PINK}{label}: {CYAN}{hex(addr)}{RESET}")

print("\n\033[92mAssembly successful... The output is printed in the machine_code.txt file!!\033[0m\n")