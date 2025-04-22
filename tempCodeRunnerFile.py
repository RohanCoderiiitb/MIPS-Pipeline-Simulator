import random
from typing import List, Dict, Tuple, Optional, Set

class Instruction:
    def __init__(self, text: str, index: int):
        self.text = text
        self.index = index
        self.is_nop = text == "NOP"  # Move this definition earlier
        self.type = self.determine_type()
        self.dest_reg = self.get_dest_reg()
        self.src_regs = self.get_src_regs()
        self.branch_target = self.get_branch_target()
        self.executed = False
        self.mem_cycles = 0  # Used to track multi-cycle memory instructions
        
    def determine_type(self) -> str:
        if self.is_nop:
            return "NOP"
        if self.text.startswith("add ") or self.text.startswith("sub "):
            return "R_TYPE"
        elif self.text.startswith("addi ") or self.text.startswith("slti "):
            return "I_TYPE"
        elif self.text.startswith("lw "):
            return "LOAD"
        elif self.text.startswith("sw "):
            return "STORE"
        elif self.text.startswith("beq ") or self.text.startswith("bne "):
            return "BRANCH"
        elif self.text.startswith("j "):
            return "JUMP"
        else:
            return "UNKNOWN"
    
    def get_dest_reg(self) -> Optional[str]:
        if self.is_nop or self.type == "STORE" or self.type == "BRANCH" or self.type == "JUMP":
            return None
        
        parts = self.text.replace(",", "").split()
        if len(parts) > 1:
            return parts[1]
        return None
    
    def get_src_regs(self) -> List[str]:
        if self.is_nop:
            return []
            
        parts = self.text.replace(",", "").split()
        
        if self.type == "R_TYPE":  # add $d, $s, $t
            return [parts[2], parts[3]]
        elif self.type == "I_TYPE":  # addi $t, $s, imm or slti $t, $s, imm
            if parts[2] == "$zero":
                return []
            return [parts[2]]
        elif self.type == "LOAD":  # lw $t, offset($s)
            base_reg = parts[2].split('(')[1].strip(')')
            if base_reg == "$zero":
                return []
            return [base_reg]
        elif self.type == "STORE":  # sw $t, offset($s)
            base_reg = parts[2].split('(')[1].strip(')')
            src_regs = [parts[1]]
            if base_reg != "$zero":
                src_regs.append(base_reg)
            return src_regs
        elif self.type == "BRANCH":  # beq $s, $t, label
            return [parts[1], parts[2]]
        elif self.type == "JUMP":  # j label
            return []
        
        return []
    
    def get_branch_target(self) -> Optional[int]:
        if self.type == "BRANCH":
            parts = self.text.replace(",", "").split()
            try:
                return int(parts[3])
            except (IndexError, ValueError):
                return None
        elif self.type == "JUMP":
            parts = self.text.split()
            try:
                return int(parts[1])
            except (IndexError, ValueError):
                return None
        return None

    def __str__(self):
        if self.is_nop:
            return "nop"
        # Get the first word of the instruction for display
        return self.text.split()[0]


class PipelineSimulator:
    def __init__(self, instructions):
        self.instruction_memory = instructions
        self.pc = 0
        self.cycle = 0
        self.pipeline = {
            "IF": None,
            "ID": None,
            "EX": None,
            "MEM": None,
            "WB": None
        }
        self.timeline = []  # Will store the state of the pipeline at each cycle
        self.stall_count = 0
        self.load_stalls = 0
        self.mem_delay_cycles = 0
        self.branch_delay_slots_used = 0
        self.branch_delay_slots_wasted = 0
        self.executed_instructions = 0
        self.memory_access_time = 2  # Configure to 2 or 3 cycles for memory operations
        self.branched = False
        
    def detect_raw_hazard(self, instr) -> bool:
        """Detect Read-After-Write hazards between the instruction about to enter EX and instructions in EX/MEM/WB"""
        if instr is None or not instr.src_regs:
            return False
            
        # Check if any source register is a destination of an instruction in the pipeline
        for reg in instr.src_regs:
            if reg == "$zero":  # $zero is always 0, no hazard
                continue
                
            # Check EX stage (1 cycle away)
            if self.pipeline["EX"] and self.pipeline["EX"].dest_reg == reg:
                return True
                
            # Check MEM stage (2 cycles away)
            if self.pipeline["MEM"] and self.pipeline["MEM"].dest_reg == reg:
                # Special case for LOAD: need an extra stall
                if self.pipeline["MEM"].type == "LOAD":
                    return True
                    
        return False
    
    def detect_load_hazard(self, instr) -> bool:
        """Detect hazard from a load operation where the loaded value is needed immediately after"""
        if instr is None or not instr.src_regs:
            return False
            
        for reg in instr.src_regs:
            if reg == "$zero":
                continue
                
            # Check if previous instruction is a load with this reg as destination
            if (self.pipeline["ID"] and self.pipeline["ID"].type == "LOAD" and 
                self.pipeline["ID"].dest_reg == reg):
                # This is a load hazard
                return True
                
        return False
    
    def simulate(self):
        """Run the simulation until all instructions are executed"""
        while True:
            # Store the current state of the pipeline for visualization
            self.record_pipeline_state()
            
            # Increment cycle counter
            self.cycle += 1
            
            # Execute pipeline stages in reverse order to avoid overwriting
            self.writeback_stage()
            self.memory_stage()
            self.execute_stage()
            self.decode_stage()
            self.fetch_stage()
            
            # Check if simulation is complete
            if (self.pc >= len(self.instruction_memory) and 
                not self.pipeline["IF"] and 
                not self.pipeline["ID"] and 
                not self.pipeline["EX"] and 
                not self.pipeline["MEM"] and 
                not self.pipeline["WB"]):
                break
    
    def record_pipeline_state(self):
        """Record the current state of the pipeline for visualization"""
        state = {
            "cycle": self.cycle,
            "IF": self.pipeline["IF"].text if self.pipeline["IF"] else None,
            "ID": self.pipeline["ID"].text if self.pipeline["ID"] else None,
            "EX": self.pipeline["EX"].text if self.pipeline["EX"] else None,
            "MEM": self.pipeline["MEM"],
            "WB": self.pipeline["WB"].text if self.pipeline["WB"] else None
        }
        self.timeline.append(state)
    
    def fetch_stage(self):
        """Fetch the next instruction from memory"""
        # Don't fetch if there's already an instruction in IF or we're at the end
        if self.pipeline["IF"] or self.pc >= len(self.instruction_memory):
            return
            
        # If a branch was taken, we need to insert a NOP
        if self.branched:
            self.pipeline["IF"] = Instruction("NOP", -1)
            self.branched = False
            return
            
        # Fetch the next instruction
        instr_text = self.instruction_memory[self.pc]
        self.pipeline["IF"] = Instruction(instr_text, self.pc)
        self.pc += 1
    
    def decode_stage(self):
        """Decode the instruction and check for hazards"""
        # Nothing to decode if IF is empty
        if not self.pipeline["IF"]:
            self.pipeline["ID"] = None
            return
            
        # Move instruction from IF to ID
        instr = self.pipeline["IF"]
        
        # Check for hazards that would require stalling
        stall_needed = self.detect_raw_hazard(self.pipeline["ID"]) or self.detect_load_hazard(self.pipeline["ID"])
        
        if stall_needed:
            # Insert a bubble (no operation) and keep the IF instruction where it is
            self.stall_count += 1
            if self.detect_load_hazard(self.pipeline["ID"]):
                self.load_stalls += 1
            self.pipeline["ID"] = None
            return
            
        # Process branch/jump in decode stage
        if instr and (instr.type == "BRANCH" or instr.type == "JUMP"):
            target = instr.branch_target
            if target is not None:
                # For simplicity, we'll assume branches are always taken
                self.pc = target
                self.branched = True
                
                # Check if the branch delay slot contains a useful instruction
                if self.pc < len(self.instruction_memory) and self.instruction_memory[self.pc-1] != "NOP":
                    self.branch_delay_slots_used += 1
                else:
                    self.branch_delay_slots_wasted += 1
        
        # Move instruction from IF to ID
        self.pipeline["ID"] = instr
        self.pipeline["IF"] = None
    
    def execute_stage(self):
        """Execute the instruction"""
        # Move instruction from ID to EX
        if self.pipeline["ID"]:
            self.pipeline["EX"] = self.pipeline["ID"]
            self.pipeline["ID"] = None
            if not self.pipeline["EX"].is_nop:  # Don't count NOPs as executed instructions
                self.executed_instructions += 1
        else:
            self.pipeline["EX"] = None
    
    def memory_stage(self):
        """Process memory operations"""
        # Check if MEM has a multi-cycle memory operation in progress
        if self.pipeline["MEM"] and self.pipeline["MEM"].mem_cycles > 0:
            # Still processing a memory operation
            self.pipeline["MEM"].mem_cycles -= 1
            if self.pipeline["MEM"].mem_cycles > 0:
                # Stall the pipeline by not moving anything from EX to MEM
                self.mem_delay_cycles += 1
                return
        
        # Move instruction from EX to MEM
        if self.pipeline["EX"]:
            instr = self.pipeline["EX"]
            self.pipeline["MEM"] = instr
            self.pipeline["EX"] = None
            
            # Set memory cycles for LOAD/STORE operations
            if instr.type in ["LOAD", "STORE"]:
                instr.mem_cycles = self.memory_access_time - 1  # -1 because we're already using one cycle
                if instr.mem_cycles > 0:
                    # Stall the pipeline for remaining cycles
                    self.mem_delay_cycles += instr.mem_cycles
        else:
            self.pipeline["MEM"] = None
    
    def writeback_stage(self):
        """Write results back to registers"""
        # Move instruction from MEM to WB only if MEM is not stalled
        if self.pipeline["MEM"] and self.pipeline["MEM"].mem_cycles == 0:
            self.pipeline["WB"] = self.pipeline["MEM"]
            self.pipeline["MEM"] = None
        else:
            self.pipeline["WB"] = None
    
    def print_timeline(self):
        """Print the pipeline execution timeline"""
        print("\nPipeline Timing Table:")
        header = f"| {'Cycle':<6} | {'IF':<10} | {'ID':<10} | {'EX':<10} | {'MEM':<10} | {'WB':<10} |"
        separator = "|" + "-" * 8 + "|" + "-" * 12 + "|" + "-" * 12 + "|" + "-" * 12 + "|" + "-" * 12 + "|" + "-" * 12 + "|"
        
        print(header)
        print(separator)
        
        for state in self.timeline:
            cycle = state["cycle"]
            if_stage = self._format_instr(state["IF"])
            id_stage = self._format_instr(state["ID"])
            ex_stage = self._format_instr(state["EX"])
            
            # Handle multi-cycle memory operations
            mem_stage = "None"
            if isinstance(state["MEM"], Instruction):
                if state["MEM"].mem_cycles > 0:
                    mem_stage = f"{state['MEM'].text.split()[0]} ({state['MEM'].mem_cycles + 1})"
                else:
                    mem_stage = state["MEM"].text.split()[0]
                    
            wb_stage = self._format_instr(state["WB"])
            
            row = f"| {cycle:<6} | {if_stage:<10} | {id_stage:<10} | {ex_stage:<10} | {mem_stage:<10} | {wb_stage:<10} |"
            print(row)
    
    def _format_instr(self, instr):
        """Format instruction text for display"""
        if not instr:
            return "None"
        if isinstance(instr, str):
            if instr == "NOP":
                return "nop"
            return instr.split()[0]  # Return just the opcode
        return instr
    
    def print_statistics(self):
        """Print performance statistics"""
        print("\nSimulation Statistics:")
        print(f"Total clock cycles: {self.cycle}")
        print(f"Total instructions executed: {self.executed_instructions}")
        print(f"Total stalls: {self.stall_count}")
        print(f"  - Load stalls: {self.load_stalls}")
        print(f"  - Memory delay cycles: {self.mem_delay_cycles}")
        print(f"Branch delay slot utilization:")
        total_branches = self.branch_delay_slots_used + self.branch_delay_slots_wasted
        if total_branches > 0:
            utilization = (self.branch_delay_slots_used / total_branches) * 100
            print(f"  - Effective: {self.branch_delay_slots_used} ({utilization:.2f}%)")
            print(f"  - Wasted: {self.branch_delay_slots_wasted}")
        else:
            print("  - No branches executed")
        if self.executed_instructions > 0:
            print(f"CPI (Cycles Per Instruction): {self.cycle / self.executed_instructions:.2f}")


def main():
    # Sample MIPS code
    instruction_memory = [
        "addi $t0, $zero, 0",      # 0: t0 = 0 (loop counter)
        "addi $s0, $zero, 0",      # 1: s0 = 0 (sum)
        "addi $t3, $zero, 0",      # 2: t3 = 0 (memory pointer)
        "slti $t1, $t0, 10",       # 3: t1 = 1 if t0 < 10, else 0
        "beq $t1, $zero, 5",       # 4: if t1 == 0, branch to index 10 (sw)
        "lw $t2, 0($t3)",          # 5: load array[t3] into t2
        "add $s0, $s0, $t2",       # 6: s0 += t2
        "addi $t0, $t0, 1",        # 7: t0++
        "addi $t3, $t3, 4",        # 8: t3 += 4 (next element)
        "j 3",                     # 9: jump to index 3 (slti)
        "sw $s0, 40($zero)",       # 10: store sum at memory[40]
    ]
    
    # Create and run the simulator
    simulator = PipelineSimulator(instruction_memory)
    simulator.simulate()
    simulator.print_timeline()
    simulator.print_statistics()

if __name__ == "__main__":
    main()