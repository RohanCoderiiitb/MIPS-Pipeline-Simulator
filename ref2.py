import random
from enum import Enum
from collections import namedtuple, defaultdict
import time

class Stage(Enum):
    IF = "Instruction Fetch"
    ID = "Instruction Decode"
    EX = "Execute"
    MEM = "Memory Access"
    WB = "Write Back"
    STALL = "Stalled"
    NONE = "None"

class InstructionType(Enum):
    R_TYPE = "R-Type"
    LOAD = "Load"
    STORE = "Store"
    BRANCH = "Branch"
    JUMP = "Jump"

Instruction = namedtuple('Instruction', ['address', 'opcode', 'type', 'dest_reg', 'src_reg1', 'src_reg2', 'is_taken', 'mem_cycles'])

class PipelineSimulator:
    def __init__(self, memory_latency_range=(2, 3), use_fixed_latency=False, fixed_latency=2):
        self.clock_cycle = 0
        self.instructions = []
        self.pipeline = {
            Stage.IF: None,
            Stage.ID: None,
            Stage.EX: None,
            Stage.MEM: None,
            Stage.WB: None
        }
        self.registers = {i: 0 for i in range(32)}
        self.pc = 0
        self.memory_latency_range = memory_latency_range
        self.use_fixed_latency = use_fixed_latency
        self.fixed_latency = fixed_latency
        
        # Memory access tracking
        self.mem_access_cycles = 0
        self.mem_instruction = None
        
        # Branch delay slot
        self.branch_delay_slot = False
        self.branch_target = None
        
        # Statistics
        self.total_instructions = 0
        self.total_stalls = 0
        self.load_stalls = 0
        self.branch_delay_slots_used = 0
        self.memory_delay_cycles = 0
        self.pipeline_log = []
        
        # Register for data hazard tracking
        self.executing_registers = set()
        self.memory_registers = set()
        
    def load_program(self, instructions):
        self.instructions = instructions
        self.total_instructions = len(instructions)
        
    def fetch_instruction(self):
        if self.pc >= len(self.instructions):
            return None
        return self.instructions[self.pc]
    
    def get_memory_latency(self):
        if self.use_fixed_latency:
            return self.fixed_latency
        return random.randint(self.memory_latency_range[0], self.memory_latency_range[1])
    
    def advance_pipeline(self):
        self.clock_cycle += 1
        
        # Create a log entry for this cycle
        cycle_log = {
            'cycle': self.clock_cycle,
            'stages': {stage.name: None for stage in Stage if stage != Stage.STALL and stage != Stage.NONE},
            'pc': self.pc,
            'stalled': False
        }
        
        # Write Back Stage - Always completes
        if self.pipeline[Stage.WB] is not None:
            instr = self.pipeline[Stage.WB]
            cycle_log['stages']['WB'] = f"{instr.opcode} (Addr: {instr.address})"
            
            # Update register file if needed
            if instr.type in [InstructionType.R_TYPE, InstructionType.LOAD] and instr.dest_reg is not None:
                self.registers[instr.dest_reg] = random.randint(1, 100)  # Simulated value
            
            self.pipeline[Stage.WB] = None
        
        # Memory Stage - May take multiple cycles
        if self.mem_access_cycles > 0:
            # Memory operation in progress
            cycle_log['stages']['MEM'] = f"{self.mem_instruction.opcode} (Addr: {self.mem_instruction.address}) - Cycle {self.mem_instruction.mem_cycles - self.mem_access_cycles + 1}/{self.mem_instruction.mem_cycles}"
            cycle_log['stalled'] = True
            self.mem_access_cycles -= 1
            self.memory_delay_cycles += 1
            self.total_stalls += 1
            
            if self.mem_access_cycles == 0:
                # Memory operation complete
                self.pipeline[Stage.WB] = self.mem_instruction
                self.pipeline[Stage.MEM] = None
                self.mem_instruction = None
                
                # Free up registers after MEM stage for loads
                if self.pipeline[Stage.WB].type == InstructionType.LOAD and self.pipeline[Stage.WB].dest_reg is not None:
                    self.memory_registers.discard(self.pipeline[Stage.WB].dest_reg)
        
        elif self.pipeline[Stage.MEM] is not None:
            instr = self.pipeline[Stage.MEM]
            cycle_log['stages']['MEM'] = f"{instr.opcode} (Addr: {instr.address})"
            
            if instr.type in [InstructionType.LOAD, InstructionType.STORE]:
                # Start memory operation
                latency = instr.mem_cycles
                if latency > 1:
                    self.mem_instruction = instr
                    self.mem_access_cycles = latency - 1
                    cycle_log['stalled'] = True
                    return cycle_log
                
            # Move to WB if not a multi-cycle memory operation
            self.pipeline[Stage.WB] = self.pipeline[Stage.MEM]
            self.pipeline[Stage.MEM] = None
            
            # Free up registers after MEM stage for loads
            if self.pipeline[Stage.WB].type == InstructionType.LOAD and self.pipeline[Stage.WB].dest_reg is not None:
                self.memory_registers.discard(self.pipeline[Stage.WB].dest_reg)
        
        # Execute Stage
        if self.pipeline[Stage.EX] is not None:
            instr = self.pipeline[Stage.EX]
            cycle_log['stages']['EX'] = f"{instr.opcode} (Addr: {instr.address})"
            
            # Branch handling
            if instr.type == InstructionType.BRANCH or instr.type == InstructionType.JUMP:
                if instr.is_taken:
                    self.branch_delay_slot = True
                    self.branch_target = instr.address + random.randint(1, 10)  # Simulating a branch target
                    self.branch_delay_slots_used += 1
            
            # Move to MEM
            self.pipeline[Stage.MEM] = self.pipeline[Stage.EX]
            self.pipeline[Stage.EX] = None
            
            # Free up registers after EX stage
            if self.pipeline[Stage.MEM].dest_reg is not None:
                self.executing_registers.discard(self.pipeline[Stage.MEM].dest_reg)
                
            # Mark memory-bound registers
            if self.pipeline[Stage.MEM].type == InstructionType.LOAD and self.pipeline[Stage.MEM].dest_reg is not None:
                self.memory_registers.add(self.pipeline[Stage.MEM].dest_reg)
        
        # Instruction Decode Stage
        if self.pipeline[Stage.ID] is not None:
            instr = self.pipeline[Stage.ID]
            cycle_log['stages']['ID'] = f"{instr.opcode} (Addr: {instr.address})"
            
            # Check for data hazards
            data_hazard = False
            if instr.src_reg1 is not None and (instr.src_reg1 in self.executing_registers or instr.src_reg1 in self.memory_registers):
                data_hazard = True
            if instr.src_reg2 is not None and (instr.src_reg2 in self.executing_registers or instr.src_reg2 in self.memory_registers):
                data_hazard = True
                
            if data_hazard:
                cycle_log['stalled'] = True
                self.total_stalls += 1
                if any(reg in self.memory_registers for reg in [instr.src_reg1, instr.src_reg2] if reg is not None):
                    self.load_stalls += 1
                return cycle_log  # Stall the pipeline
            
            # Move to EX
            self.pipeline[Stage.EX] = self.pipeline[Stage.ID]
            self.pipeline[Stage.ID] = None
            
            # Mark executing registers
            if self.pipeline[Stage.EX].dest_reg is not None:
                self.executing_registers.add(self.pipeline[Stage.EX].dest_reg)
        
        # Instruction Fetch Stage
        if self.pipeline[Stage.IF] is not None:
            instr = self.pipeline[Stage.IF]
            cycle_log['stages']['IF'] = f"{instr.opcode} (Addr: {instr.address})"
            
            # Move to ID
            self.pipeline[Stage.ID] = self.pipeline[Stage.IF]
            self.pipeline[Stage.IF] = None
        
        # Fetch new instruction if possible
        if self.branch_delay_slot:
            # Handle the branch delay slot
            self.branch_delay_slot = False
            next_instr = self.fetch_instruction()
            if next_instr:
                cycle_log['stages']['IF'] = f"{next_instr.opcode} (Addr: {next_instr.address})"
                self.pipeline[Stage.IF] = next_instr
                self.pc += 1
            
            # After the delay slot, jump to branch target
            if self.branch_target is not None:
                # In a real processor, we'd update PC to branch target
                # For our simulation, just increment to the next instruction
                self.pc = min(self.pc + 1, len(self.instructions))
                self.branch_target = None
        else:
            next_instr = self.fetch_instruction()
            if next_instr:
                cycle_log['stages']['IF'] = f"{next_instr.opcode} (Addr: {next_instr.address})"
                self.pipeline[Stage.IF] = next_instr
                self.pc += 1
        
        self.pipeline_log.append(cycle_log)
        return cycle_log
    
    def run_simulation(self):
        while (self.pc < len(self.instructions) or 
               any(self.pipeline[stage] is not None for stage in self.pipeline) or 
               self.mem_access_cycles > 0):
            self.advance_pipeline()
            
    def print_timing_table(self):
        print("\nPipeline Timing Table:")
        print("=" * 100)
        print(f"{'Cycle':<6}{'IF':<25}{'ID':<25}{'EX':<25}{'MEM':<25}{'WB':<25}")
        print("-" * 100)
        
        for log in self.pipeline_log:
            cycle = log['cycle']
            stages = log['stages']
            if_val = stages['IF'] if stages['IF'] else "-"
            id_val = stages['ID'] if stages['ID'] else "-"
            ex_val = stages['EX'] if stages['EX'] else "-"
            mem_val = stages['MEM'] if stages['MEM'] else "-"
            wb_val = stages['WB'] if stages['WB'] else "-"
            
            print(f"{cycle:<6}{if_val:<25}{id_val:<25}{ex_val:<25}{mem_val:<25}{wb_val:<25}")
            
    def print_statistics(self):
        print("\nSimulation Statistics:")
        print("=" * 50)
        print(f"Total Clock Cycles: {self.clock_cycle}")
        print(f"Total Instructions Executed: {self.total_instructions}")
        print(f"Total Stalls: {self.total_stalls}")
        print(f"  - Load Stalls: {self.load_stalls}")
        print(f"Branch Delay Slots Used: {self.branch_delay_slots_used}")
        print(f"Memory Delay Cycles: {self.memory_delay_cycles}")
        
        if self.total_instructions > 0:
            cpi = self.clock_cycle / self.total_instructions
            print(f"Cycles Per Instruction (CPI): {cpi:.2f}")

def generate_test_program(size=20):
    instructions = []
    registers = list(range(10))  # Using registers 0-9 for simplicity
    
    for i in range(size):
        instr_type = random.choice(list(InstructionType))
        opcode = None
        dest_reg = None
        src_reg1 = None
        src_reg2 = None
        is_taken = False
        mem_cycles = 1
        
        if instr_type == InstructionType.R_TYPE:
            opcodes = ["ADD", "SUB", "AND", "OR", "XOR", "SLT"]
            opcode = random.choice(opcodes)
            dest_reg = random.choice(registers)
            src_reg1 = random.choice(registers)
            src_reg2 = random.choice(registers)
        
        elif instr_type == InstructionType.LOAD:
            opcodes = ["LW", "LH", "LB"]
            opcode = random.choice(opcodes)
            dest_reg = random.choice(registers)
            src_reg1 = random.choice(registers)  # Base register
            mem_cycles = random.randint(2, 3)  # Multi-cycle memory access
        
        elif instr_type == InstructionType.STORE:
            opcodes = ["SW", "SH", "SB"]
            opcode = random.choice(opcodes)
            src_reg1 = random.choice(registers)  # Base register
            src_reg2 = random.choice(registers)  # Value to store
            mem_cycles = random.randint(2, 3)  # Multi-cycle memory access
        
        elif instr_type == InstructionType.BRANCH:
            opcodes = ["BEQ", "BNE", "BLT", "BGT"]
            opcode = random.choice(opcodes)
            src_reg1 = random.choice(registers)
            src_reg2 = random.choice(registers)
            is_taken = random.choice([True, False])
        
        elif instr_type == InstructionType.JUMP:
            opcodes = ["J", "JAL", "JR"]
            opcode = random.choice(opcodes)
            if opcode == "JR":
                src_reg1 = random.choice(registers)
            is_taken = True
        
        instructions.append(Instruction(
            address=i*4,  # Simple address calculation
            opcode=opcode,
            type=instr_type,
            dest_reg=dest_reg,
            src_reg1=src_reg1,
            src_reg2=src_reg2,
            is_taken=is_taken,
            mem_cycles=mem_cycles
        ))
    
    return instructions

def main():
    print("MIPS 5-Stage Pipeline Simulator with Delayed Branches and Multi-Cycle Memory Access")
    print("=" * 80)
    
    # Configuration options
    use_fixed_latency = False
    fixed_latency = 2
    program_size = 25
    
    # Generate a test program
    print(f"Generating a test program with {program_size} instructions...")
    program = generate_test_program(program_size)
    
    # Print program details
    print("\nTest Program:")
    print("=" * 50)
    for i, instr in enumerate(program):
        mem_info = f" (Memory cycles: {instr.mem_cycles})" if instr.type in [InstructionType.LOAD, InstructionType.STORE] else ""
        branch_info = f" ({'Taken' if instr.is_taken else 'Not Taken'})" if instr.type in [InstructionType.BRANCH, InstructionType.JUMP] else ""
        
        if instr.type == InstructionType.R_TYPE:
            print(f"{i:2d}: {instr.opcode} R{instr.dest_reg}, R{instr.src_reg1}, R{instr.src_reg2}")
        elif instr.type == InstructionType.LOAD:
            print(f"{i:2d}: {instr.opcode} R{instr.dest_reg}, offset(R{instr.src_reg1}){mem_info}")
        elif instr.type == InstructionType.STORE:
            print(f"{i:2d}: {instr.opcode} R{instr.src_reg2}, offset(R{instr.src_reg1}){mem_info}")
        elif instr.type == InstructionType.BRANCH:
            print(f"{i:2d}: {instr.opcode} R{instr.src_reg1}, R{instr.src_reg2}, target{branch_info}")
        elif instr.type == InstructionType.JUMP:
            if instr.opcode == "JR":
                print(f"{i:2d}: {instr.opcode} R{instr.src_reg1}{branch_info}")
            else:
                print(f"{i:2d}: {instr.opcode} target{branch_info}")
    
    # Initialize simulator
    simulator = PipelineSimulator(
        memory_latency_range=(2, 3),
        use_fixed_latency=use_fixed_latency,
        fixed_latency=fixed_latency
    )
    
    # Load program
    simulator.load_program(program)
    
    # Run simulation
    print("\nRunning simulation...")
    start_time = time.time()
    simulator.run_simulation()
    end_time = time.time()
    
    # Print results
    print(f"\nSimulation completed in {end_time - start_time:.2f} seconds.")
    simulator.print_timing_table()
    simulator.print_statistics()

if __name__ == "__main__":
    main()