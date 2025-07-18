import random
import colorama
from colorama import Fore, Back, Style
import matplotlib.pyplot as plt

colorama.init(autoreset=True)

STAGE_COLORS = {
    'IF': Fore.CYAN,
    'ID': Fore.MAGENTA,
    'EX': Fore.YELLOW,
    'MEM': Fore.GREEN,
    'WB': Fore.RED,
}

STAT_COLORS = {
    'cycles': Fore.BLUE + Style.BRIGHT,
    'instructions': Fore.GREEN + Style.BRIGHT,
    'stalls': Fore.RED + Style.BRIGHT,
    'branches': Fore.YELLOW + Style.BRIGHT,
    'efficiency': Fore.CYAN + Style.BRIGHT,
    'registers': Fore.MAGENTA + Style.BRIGHT,
}

memory = {i: i // 4 for i in range(0, 40, 4)}
registers = [0] * 32

instruction_memory = [
    "lw   $t2, 0($zero)",
    "addi $t1, $zero, 4",
    "loop:",
    "  slti $t0, $t1, 40",
    "  beq  $t0, $zero, end",
    "  lw   $t3, 0($t1)",
    "  add  $t2, $t2, $t3",
    "  sw   $t2, 0($t1)",
    "  addi $t1, $t1, 4",
    "  j    loop",
    "end:",
    "  sw   $t2, 40($zero)",
    "  nop"
]

filtered_instructions = []
label_to_index = {}
for line in instruction_memory:
    line = line.strip()
    if line.endswith(":"):
        label = line[:-1]
        label_to_index[label] = len(filtered_instructions)
    elif line:
        filtered_instructions.append(line)

def parse_register(reg):
    reg_map = {
        '$zero': 0, '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11, '$s0': 16,
        '$t4': 12, '$t5': 13, '$t6': 14, '$t7': 15, '$s1': 17, '$s2': 18,
        '$s3': 19, '$s4': 20, '$a0': 4, '$a1': 5, '$a2': 6, '$a3': 7,
        '$v0': 2
    }
    return reg_map.get(reg, 0)

def parse_instruction(instr):
    parts = instr.split()
    opcode = parts[0]
    if opcode == 'addi' or opcode == 'slti':
        rd, rs, imm = parts[1].strip(','), parts[2].strip(','), int(parts[3])
        return {'type': 'I', 'opcode': opcode, 'rd': parse_register(rd), 'rs': parse_register(rs), 'imm': imm}
    elif opcode == 'beq':
        rs, rt, label = parts[1].strip(','), parts[2].strip(','), parts[3]
        return {'type': 'I', 'opcode': 'beq', 'rs': parse_register(rs), 'rt': parse_register(rt), 'label': label}
    elif opcode == 'j':
        label = parts[1]
        return {'type': 'J', 'opcode': 'j', 'label': label}
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

def simulate():
    PC = 0
    cycle = 0
    total_instructions = 0
    memory_stalls = 0
    delayed_branches = 0
    load_stalls = 0
    cycles_wasted_memory = 0
    dynamic_nops_inserted = 0
    branch_slots_used = 0
    branch_instructions = 0

    IF_ID = None
    ID_EX = None
    EX_MEM = None
    MEM_WB = None
    delayed_branch = False
    branch_target = 0
    nop_count = 0
    in_branch_delay_slot = False

    pipeline_log = []

    def get_register_value(reg):
        if MEM_WB:
            instr = MEM_WB['instr']
            if ('rd' in instr and instr['rd'] == reg and instr['type'] == 'R') or \
               ('rt' in instr and instr['rt'] == reg and instr['opcode'] == 'lw') or \
               ('rd' in instr and instr['rd'] == reg and instr['type'] == 'I' and instr['opcode'] in ['addi', 'slti']):
                return MEM_WB['result']
        if EX_MEM:
            instr = EX_MEM['instr']
            if ('rd' in instr and instr['rd'] == reg and instr['type'] == 'R') or \
               ('rd' in instr and instr['rd'] == reg and instr['type'] == 'I' and instr['opcode'] in ['addi', 'slti']):
                return EX_MEM['result']
        return registers[reg]

    while True:
        cycle += 1
        current_stage = {'IF': "--", 'ID': "--", 'EX': "--", 'MEM': "--", 'WB': "--"}

        if MEM_WB:
            instr = MEM_WB['instr']
            if 'rd' in instr:
                registers[instr['rd']] = MEM_WB.get('result', 0)
            elif 'rt' in instr and instr['opcode'] == 'lw':
                registers[instr['rt']] = MEM_WB.get('result', 0)
            total_instructions += 1
            current_stage['WB'] = instr['opcode']

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
            if EX_MEM:
                current_stage['MEM'] = EX_MEM['instr']['opcode']

        if not stall:
            MEM_WB = EX_MEM
            EX_MEM = None

            if ID_EX:
                instr = ID_EX['instr']
                current_stage['EX'] = instr['opcode']
                if in_branch_delay_slot and instr['type'] != 'nop':
                    branch_slots_used += 1
                    in_branch_delay_slot = False
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
                        branch_instructions += 1
                        in_branch_delay_slot = True
                        EX_MEM = {'instr': instr, 'cycles_left': 1}
                    elif instr['opcode'] == 'lw':
                        address = ID_EX['base_value'] + instr['offset']
                        result = memory.get(address, 0)
                        EX_MEM = {'instr': instr, 'cycles_left': random.randint(2, 3), 'result': result}
                    elif instr['opcode'] == 'sw':
                        address = ID_EX['base_value'] + instr['offset']
                        memory[address] = ID_EX['rt_value']
                        EX_MEM = {'instr': instr, 'cycles_left': random.randint(2, 3)}
                elif instr['type'] == 'J' and instr['opcode'] == 'j':
                    delayed_branch = True
                    branch_target = instr['target']
                    delayed_branches += 1
                    branch_instructions += 1
                    in_branch_delay_slot = True
                    EX_MEM = {'instr': instr, 'cycles_left': 1}
                elif instr['type'] == 'nop':
                    EX_MEM = {'instr': instr, 'cycles_left': 1}
                    if in_branch_delay_slot:
                        in_branch_delay_slot = False

            if IF_ID:
                instr = parse_instruction(IF_ID['instruction'])
                rs_value = get_register_value(instr.get('rs', 0))
                rt_value = get_register_value(instr.get('rt', 0))
                base_value = get_register_value(instr.get('base', 0)) if 'base' in instr else 0
                if 'label' in instr:
                    label = instr['label']
                    target_index = label_to_index[label]
                    if instr['opcode'] == 'beq':
                        offset = target_index - (IF_ID['index'] + 1)
                        instr['offset'] = offset
                    elif instr['opcode'] == 'j':
                        instr['target'] = target_index
                    del instr['label']
                ID_EX = {'instr': instr, 'rs_value': rs_value, 'rt_value': rt_value, 'base_value': base_value, 'index': IF_ID['index']}
                current_stage['ID'] = instr['opcode']
                if instr['opcode'] in ['beq', 'j']:
                    nop_count = 4
            else:
                ID_EX = None

            if PC < len(filtered_instructions) and not stall:
                if nop_count > 0:
                    IF_ID = {'instruction': "nop", 'index': -1}
                    current_stage['IF'] = "nop"
                    nop_count -= 1
                    dynamic_nops_inserted += 1
                else:
                    IF_ID = {'instruction': filtered_instructions[PC], 'index': PC}
                    current_stage['IF'] = filtered_instructions[PC].split()[0]
                    if delayed_branch:
                        PC = branch_target
                        delayed_branch = False
                    else:
                        PC += 1
            else:
                IF_ID = None

        pipeline_log.append([cycle] + [current_stage[stage] for stage in ['IF', 'ID', 'EX', 'MEM', 'WB']])

        if PC >= len(filtered_instructions) and not any((MEM_WB, EX_MEM, ID_EX, IF_ID)):
            break

    print(f"\n{Style.BRIGHT}Pipeline Timing Table:")
    print(f"| {Style.BRIGHT}{'Cycle':5} | {STAGE_COLORS['IF']}{'IF':8} | {STAGE_COLORS['ID']}{'ID':8} | {STAGE_COLORS['EX']}{'EX':8} | {STAGE_COLORS['MEM']}{'MEM':8} | {STAGE_COLORS['WB']}{'WB':8} |")
    print("|-------|----------|----------|----------|----------|----------|")
    for entry in pipeline_log:
        cycle_num = entry[0]
        stages = entry[1:]
        print(f"| {cycle_num:5d} | ", end="")
        for idx, stage in enumerate(stages):
            stage_name = ['IF', 'ID', 'EX', 'MEM', 'WB'][idx]
            if stage and stage != "--":
                print(f"{STAGE_COLORS[stage_name]}{str(stage):8} | ", end="")
            else:
                print(f"{str(stage):8} | ", end="")
        print()

    branch_delay_effectiveness = (branch_slots_used / branch_instructions * 100) if branch_instructions > 0 else 0

    print(f"\n{Style.BRIGHT}{Fore.WHITE}Performance Statistics:")
    print(f"{STAT_COLORS['cycles']}Total clock cycles: {cycle}")
    print(f"{STAT_COLORS['instructions']}Total instructions executed: {total_instructions}")
    print(f"{STAT_COLORS['stalls']}Total stalls due to memory: {memory_stalls}")
    print(f"{STAT_COLORS['stalls']}Stalls due to loads: {load_stalls}")
    print(f"{STAT_COLORS['branches']}Delayed branches taken: {delayed_branches}")
    print(f"{STAT_COLORS['branches']}Branch delay slots used effectively: {branch_slots_used}/{branch_instructions}")
    print(f"{STAT_COLORS['efficiency']}Branch delay slot effectiveness: {branch_delay_effectiveness:.2f}%")
    print(f"{STAT_COLORS['stalls']}Dynamic NOPs inserted: {dynamic_nops_inserted}")
    print(f"{STAT_COLORS['cycles']}Cycles wasted due to memory delays: {cycles_wasted_memory}")

    ipc = total_instructions / cycle if cycle > 0 else 0
    print(f"{STAT_COLORS['efficiency']}Instructions per cycle (IPC): {ipc:.2f}")

    print(f"\n{STAT_COLORS['registers']}Final Register Values:")
    for i in range(8, 13):
        print(f"{STAT_COLORS['registers']}$t{i-8} (reg {i}): {registers[i]}")

    print(f"\n{Style.BRIGHT}{Fore.CYAN}Final Memory Values (Prefix Sum):")
    for addr in sorted(memory.keys()):
        if addr <= 40:
            print(f"{Fore.CYAN}Address {addr:2d}: {memory[addr]}")

    count_metrics = {
        'Total Cycles': cycle,
        'Instructions': total_instructions,
        'Memory Stalls': memory_stalls,
        'Load Stalls': load_stalls,
        'Delayed Branches': delayed_branches,
        'Dynamic NOPs': dynamic_nops_inserted,
        'Wasted Cycles': cycles_wasted_memory,
    }
    ratio_metrics = {
        'IPC': ipc,
        'Branch Delay Effectiveness (%)': branch_delay_effectiveness,
    }

    plt.figure(figsize=(10, 6))
    plt.barh(list(count_metrics.keys()), list(count_metrics.values()))
    plt.xlabel('Count')
    plt.title('Pipeline Performance – Raw Metrics')
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(6, 4))
    plt.bar(list(ratio_metrics.keys()), list(ratio_metrics.values()))
    plt.ylabel('Value')
    plt.title('Pipeline Performance – Efficiency Metrics')
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    simulate()
