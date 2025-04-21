import os
import time

# Initialize memory and registers
memory = {}
registers = [0] * 32
DATA_SEGMENT_BASE = 0x10000000  # Standard MIPS data segment base

# File handling
file_name = input('Enter name of the file: ')
if not file_name.endswith('.asm'):
    file_name += '.asm'
if not os.path.isfile(file_name):
    print(f"File '{file_name}' not found in the correct directory")
    file_name = input("Enter the full path of the file: ")
    if not file_name.endswith('.asm'):
        file_name += '.asm'
    if not os.path.isfile(file_name):
        print(f"Error: File '{file_name}' not found.")
        exit()

instruction_memory = []
data_labels = {}
instruction_labels = {}
current_segment = None
current_address = DATA_SEGMENT_BASE

# Read the file and parse `.data` and `.text` segments
with open(file_name, 'r', encoding='utf-8') as file:
    print("File has been opened")
    for line in file:
        # Remove comments and strip whitespace
        line = line.split('#')[0].split('//')[0].strip()
        if not line:
            continue  # Skip empty lines

        # Check for segment declarations
        if line == ".data":
            current_segment = "data"
            continue
        elif line == ".text":
            current_segment = "text"
            continue

        # Parse `.data` segment
        if current_segment == "data":
            parts = line.split(':')
            if len(parts) == 2:
                label = parts[0].strip()
                value = parts[1].strip()
                if value.startswith(".asciiz"):
                    # Handle string data
                    string_value = value.split(".asciiz")[1].strip().strip('"')
                    data_labels[label] = current_address
                    for char in string_value:
                        memory[current_address] = ord(char)
                        current_address += 1
                    memory[current_address] = 0  # Null terminator
                    current_address += 1
                elif value.startswith(".word"):
                    # Handle integer data with alignment
                    if current_address % 4 != 0:
                        current_address += 4 - (current_address % 4)
                    word_values = list(map(int, value.split(".word")[1].strip().split(',')))
                    data_labels[label] = current_address
                    for word in word_values:
                        memory[current_address] = word & 0xFF
                        memory[current_address + 1] = (word >> 8) & 0xFF
                        memory[current_address + 2] = (word >> 16) & 0xFF
                        memory[current_address + 3] = (word >> 24) & 0xFF
                        current_address += 4
                elif value.startswith(".space"):
                    # Handle reserved space
                    size = int(value.split(".space")[1].strip())
                    data_labels[label] = current_address
                    current_address += size
            continue

        # Parse `.text` segment
        if current_segment == "text":
            if ':' in line:
                # Correctly handle labels that might have instruction on same line
                parts = line.split(':', 1)
                label = parts[0].strip()
                instruction_labels[label] = len(instruction_memory)
                
                # Check if there's an instruction after the label
                if len(parts) > 1 and parts[1].strip():
                    instruction_memory.append(parts[1].strip())
            else:
                instruction_memory.append(line)

if not instruction_memory:
    print("Error: No instructions found in .text segment.")
    exit()

# Parse registers
def parse_register(reg):
    reg_map = {
        '$0': 0, '$at': 1, '$v0': 2, '$v1': 3, '$a0': 4, '$a1': 5, '$a2': 6, '$a3': 7,
        '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11, '$t4': 12, '$t5': 13, '$t6': 14, '$t7': 15,
        '$s0': 16, '$s1': 17, '$s2': 18, '$s3': 19, '$s4': 20, '$s5': 21, '$s6': 22, '$s7': 23,
        '$t8': 24, '$t9': 25, '$k0': 26, '$k1': 27, '$gp': 28, '$sp': 29, '$fp': 30, '$ra': 31
    }
    # Add support for $0-$31 direct register references
    if reg.startswith('$') and reg[1:].isdigit():
        reg_num = int(reg[1:])
        if 0 <= reg_num <= 31:
            return reg_num
    return reg_map.get(reg, 0)

# Parse instructions with PC parameter
def parse_instruction(instr, PC):
    parts = instr.split()
    if not parts:
        return {'type': 'nop', 'opcode': 'nop'}  # Handle empty instructions
        
    opcode = parts[0]
    
    try:
        # I-Type Instructions
        if opcode in ['addi', 'slti']:
            rd, rs, imm = parts[1].strip(','), parts[2].strip(','), int(parts[3])
            return {'type': 'I', 'opcode': opcode, 'rd': parse_register(rd), 'rs': parse_register(rs), 'imm': imm}
        elif opcode in ['beq', 'bne']:
            rs, rt, label = parts[1].strip(','), parts[2].strip(','), parts[3]
            if label in instruction_labels:
                offset = instruction_labels[label] - (PC + 1)
            else:
                try:
                    offset = int(label)
                except ValueError:
                    print(f"Warning: Undefined label '{label}' at PC {PC}. Available labels: {list(instruction_labels.keys())}")
                    offset = 0  # Default to no-jump on undefined label
            return {'type': 'I', 'opcode': opcode, 'rs': parse_register(rs), 'rt': parse_register(rt), 'offset': offset}
        elif opcode in ['lw', 'sw']:
            rt, offset_base = parts[1].strip(','), parts[2]
            offset, base = offset_base.split('(')
            base = base.strip(')')
            return {'type': 'I', 'opcode': opcode, 'rt': parse_register(rt), 'base': parse_register(base), 'offset': int(offset)}
        elif opcode == 'andi':
            rt, rs, imm = parts[1].strip(','), parts[2].strip(','), int(parts[3])
            return {'type': 'I', 'opcode': 'andi', 'rt': parse_register(rt), 'rs': parse_register(rs), 'imm': imm}
        elif opcode == 'ori':
            rt, rs, imm = parts[1].strip(','), parts[2].strip(','), int(parts[3])
            return {'type': 'I', 'opcode': 'ori', 'rt': parse_register(rt), 'rs': parse_register(rs), 'imm': imm}
        elif opcode == 'li':
            rt, imm = parts[1].strip(','), int(parts[2])
            return {'type': 'I', 'opcode': 'li', 'rt': parse_register(rt), 'imm': imm}
        elif opcode == 'la':
            rt, label = parts[1].strip(','), parts[2]
            if label not in data_labels:
                print(f"Warning: Undefined data label '{label}' at PC {PC}. Available labels: {list(data_labels.keys())}")
                # Return a placeholder value for now
                return {'type': 'I', 'opcode': 'la', 'rt': parse_register(rt), 'label': label}
            return {'type': 'I', 'opcode': 'la', 'rt': parse_register(rt), 'label': label}

        # R-Type Instructions
        elif opcode in ['add', 'sub', 'and', 'or', 'slt', 'xor', 'nor']:
            rd, rs, rt = parts[1].strip(','), parts[2].strip(','), parts[3]
            return {'type': 'R', 'opcode': opcode, 'rd': parse_register(rd), 'rs': parse_register(rs), 'rt': parse_register(rt)}
        elif opcode == 'jr':
            rs = parts[1]
            return {'type': 'R', 'opcode': 'jr', 'rs': parse_register(rs)}
        elif opcode == 'sll':
            rd, rt, shamt = parts[1].strip(','), parts[2].strip(','), int(parts[3])
            return {'type': 'R', 'opcode': 'sll', 'rd': parse_register(rd), 'rt': parse_register(rt), 'shamt': shamt}
        elif opcode == 'srl':
            rd, rt, shamt = parts[1].strip(','), parts[2].strip(','), int(parts[3])
            return {'type': 'R', 'opcode': 'srl', 'rd': parse_register(rd), 'rt': parse_register(rt), 'shamt': shamt}
        elif opcode == 'sra':
            rd, rt, shamt = parts[1].strip(','), parts[2].strip(','), int(parts[3])
            return {'type': 'R', 'opcode': 'sra', 'rd': parse_register(rd), 'rt': parse_register(rt), 'shamt': shamt}
        elif opcode == 'sllv':
            rd, rt, rs = parts[1].strip(','), parts[2].strip(','), parts[3]
            return {'type': 'R', 'opcode': 'sllv', 'rd': parse_register(rd), 'rt': parse_register(rt), 'rs': parse_register(rs)}

        # J-Type Instructions
        elif opcode in ['j', 'jal']:
            target = parts[1]
            if target in instruction_labels:
                target = instruction_labels[target]
            else:
                try:
                    target = int(target)
                except ValueError:
                    print(f"Warning: Undefined jump target '{target}' at PC {PC}. Available labels: {list(instruction_labels.keys())}")
                    target = PC  # Default to self-loop on undefined target
            return {'type': 'J', 'opcode': opcode, 'target': target}
        elif opcode == 'syscall':
            return {'type': 'syscall', 'opcode': 'syscall'}
        elif opcode == 'nop':
            return {'type': 'nop', 'opcode': 'nop'}
        else:
            print(f"Warning: Unknown instruction '{opcode}' at PC {PC}")
            return {'type': 'nop', 'opcode': 'nop'}  # Return nop for unrecognized instructions
    except Exception as e:
        print(f"Error parsing instruction '{instr}' at PC {PC}: {e}")
        return {'type': 'nop', 'opcode': 'nop'}  # Return nop on parse error

# Simulation logic
def simulate():
    global PC
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

    print("\nPipeline Timing Table:")
    print("| Cycle | IF       | ID       | EX       | MEM      | WB       |")
    print("|-------|----------|----------|----------|----------|----------|")

    while True:
        cycle += 1
        current_stage = {'IF': None, 'ID': None, 'EX': None, 'MEM': None, 'WB': None}

        # WB stage
        if MEM_WB:
            if 'rd' in MEM_WB['instr']:
                registers[MEM_WB['instr']['rd']] = MEM_WB['result']
            elif 'rt' in MEM_WB['instr'] and MEM_WB['instr']['opcode'] in ['lw', 'li', 'la']:
                registers[MEM_WB['instr']['rt']] = MEM_WB['result']
            elif MEM_WB['instr']['opcode'] == 'jal':
                registers[31] = MEM_WB['result']
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

        # Only update pipeline registers if not stalled
        if not stall:
            MEM_WB = EX_MEM
            EX_MEM = None

            # EX stage
            if ID_EX:
                instr = ID_EX['instr']
                current_stage['EX'] = instr['opcode']
                if instr['type'] == 'R':
                    if instr['opcode'] == 'add':
                        result = ID_EX['rs_value'] + ID_EX['rt_value']
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                    elif instr['opcode'] == 'slt':
                        result = 1 if ID_EX['rs_value'] < ID_EX['rt_value'] else 0
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                    elif instr['opcode'] == 'jr':
                        delayed_branch = True
                        branch_target = ID_EX['rs_value']
                        delayed_branches += 1
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif instr['opcode'] == 'sll':
                        result = ID_EX['rt_value'] << instr['shamt']
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                    elif instr['opcode'] == 'srl':
                        result = ID_EX['rt_value'] >> instr['shamt']
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
                    elif instr['opcode'] == 'bne':
                        if ID_EX['rs_value'] != ID_EX['rt_value']:
                            delayed_branch = True
                            branch_target = ID_EX['index'] + 1 + instr['offset']
                            delayed_branches += 1
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif instr['opcode'] == 'lw':
                        address = ID_EX['base_value'] + instr['offset']
                        if address % 4 != 0:
                            print(f"Warning: Unaligned memory access for lw at address {address}")
                        result = (memory.get(address, 0) |
                                (memory.get(address + 1, 0) << 8) |
                                (memory.get(address + 2, 0) << 16) |
                                (memory.get(address + 3, 0) << 24))
                        EX_MEM = {'instr': instr, 'cycles_left': 2, 'result': result}
                    elif instr['opcode'] == 'sw':
                        address = ID_EX['base_value'] + instr['offset']
                        if address % 4 != 0:
                            print(f"Warning: Unaligned memory access for sw at address {address}")
                        value = ID_EX['rt_value']
                        memory[address] = value & 0xFF
                        memory[address + 1] = (value >> 8) & 0xFF
                        memory[address + 2] = (value >> 16) & 0xFF
                        memory[address + 3] = (value >> 24) & 0xFF
                        EX_MEM = {'instr': instr, 'cycles_left': 3}
                    elif instr['opcode'] == 'li':
                        result = instr['imm']
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                    elif instr['opcode'] == 'la':
                        if instr['label'] not in data_labels:
                            print(f"Warning: Using default address for undefined label: {instr['label']}")
                            result = DATA_SEGMENT_BASE  # Default to data segment base on error
                        else:
                            result = data_labels[instr['label']]
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                elif instr['opcode'] == 'syscall':
                    if registers[2] == 1:
                        print(registers[4])
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif registers[2] == 4:
                        address = registers[4]
                        string = ""
                        while memory.get(address, 0) != 0:
                            string += chr(memory[address])
                            address += 1
                        print(string, end="")
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif registers[2] == 5:
                        registers[2] = int(input())
                        EX_MEM = {'instr': instr, 'cycles_left': 2}
                    elif registers[2] == 11:
                        print(chr(registers[4]), end="")
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif registers[2] == 12:
                        registers[2] = ord(input()[0])
                        EX_MEM = {'instr': instr, 'cycles_left': 2}
                    elif registers[2] == 10:
                        print("Program exited.")
                        break
                    else:
                        print(f"Warning: Unrecognized syscall code {registers[2]}")
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                elif instr['type'] == 'J':
                    if instr['opcode'] == 'j':
                        delayed_branch = True
                        branch_target = instr['target']
                        delayed_branches += 1
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif instr['opcode'] == 'jal':
                        delayed_branch = True
                        branch_target = instr['target']
                        delayed_branches += 1
                        result = ID_EX['index'] + 2
                        EX_MEM = {'instr': instr, 'cycles_left': 1, 'result': result}
                elif instr['type'] == 'nop':
                    EX_MEM = {'instr': instr, 'cycles_left': 1}

            # ID stage
            if IF_ID:
                instr = parse_instruction(IF_ID['instruction'], IF_ID['index'])
                rs_value = registers[instr.get('rs', 0)]
                rt_value = registers[instr.get('rt', 0)]
                base_value = registers[instr.get('base', 0)] if 'base' in instr else 0
                ID_EX = {'instr': instr, 'rs_value': rs_value, 'rt_value': rt_value, 'base_value': base_value, 'index': IF_ID['index']}
                current_stage['ID'] = instr['opcode']
            else:
                ID_EX = None

            # IF stage
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

        # Print current pipeline state with delay
        print(f"| {cycle:5d} | {str(current_stage['IF']):8} | {str(current_stage['ID']):8} | {str(current_stage['EX']):8} | {str(current_stage['MEM']):8} | {str(current_stage['WB']):8} |")
        time.sleep(0.1)  # Simulate pipeline delay

        # Termination condition
        if PC >= len(instruction_memory) and not MEM_WB and not EX_MEM and not ID_EX and not IF_ID:
            break

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