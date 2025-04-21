#!/usr/bin/env python3
import sys
import re
import random
from collections import namedtuple

# Representation for instructions and pipeline registers
def Instr(pc, op, args, raw): pass
Instr = namedtuple('Instr', 'pc op args raw')
PipelineReg = namedtuple('PipelineReg', 'instr stage remaining_mem result')

class PipelineSimulator:
    def __init__(self, asm_file, mem_latency=(2,3)):
        self.mem_min, self.mem_max = mem_latency
        self.regs = [0]*32
        self.mem = {}           # simple memory model
        self.pc_map = {}
        self.instrs = []
        self.trace = []
        self.pipe = [None]*5    # IF, ID, EX, MEM, WB
        self.cycle = 0
        self.stalls_load = 0
        self.stalls_mem = 0
        self.branch_count = 0
        self.parse_asm(asm_file)
        self.total_instructions = len(self.instrs)
        self.pc = 0

    def parse_asm(self, filename):
        lines = open(filename).read().splitlines()
        pc = 0
        # first pass: labels
        for raw in lines:
            line = raw.split('#')[0].strip()
            if not line or line.startswith('.'):
                continue
            if ':' in line:
                lbl = line.split(':')[0]
                self.pc_map[lbl] = pc
                if line.split(':')[1].strip(): pc += 4
            else:
                pc += 4
        # second pass: instructions
        pc = 0
        for raw in lines:
            line = raw.split('#')[0].strip()
            if not line or line.startswith('.'):
                continue
            if ':' in line:
                parts = line.split(':',1)
                line = parts[1].strip()
                if not line: continue
            tokens = re.split(r'[\s(),]+', line)
            op = tokens[0]
            args = tokens[1:]
            self.instrs.append(Instr(pc, op, args, line))
            self.trace.append([])
            pc += 4

    def reg_idx(self, reg):
        r = reg.strip().lstrip('$')
        if r.isdigit(): return int(r)
        m = {
            'zero':0,'at':1,'v0':2,'v1':3,
            'a0':4,'a1':5,'a2':6,'a3':7,
            't0':8,'t1':9,'t2':10,'t3':11,'t4':12,'t5':13,'t6':14,'t7':15,
            's0':16,'s1':17,'s2':18,'s3':19,'s4':20,'s5':21,'s6':22,'s7':23,
            't8':24,'t9':25,'k0':26,'k1':27,'gp':28,'sp':29,'fp':30,'ra':31
        }
        return m.get(r, 0)

    def step(self):
        self.cycle += 1
        comments = []
        # --- WB stage ---
        wb = self.pipe[4]
        if wb and wb.result is not None:
            dest = wb.instr.args[0] if wb.instr.args else None
            if dest and dest.startswith('$'):
                self.regs[self.reg_idx(dest)] = wb.result
        # shift pipeline
        self.pipe[4] = self.pipe[3]

        # --- MEM stage ---
        mem = self.pipe[3]
        if mem:
            ins = mem.instr
            if mem.stage=='MEM' and mem.remaining_mem > 1:
                self.pipe[3] = mem._replace(remaining_mem=mem.remaining_mem-1)
                self.stalls_mem += 1
                comments.append(f"MEM stall for {ins.raw}")
            else:
                # complete MEM -> WB
                self.pipe[4] = PipelineReg(ins, 'WB', 0, mem.result)
                self.pipe[3] = self.pipe[2]
        else:
            self.pipe[3] = self.pipe[2]

        # --- EX stage ---
        ex = self.pipe[2]
        flush = False
        if ex and ex.stage=='EX':
            ins = ex.instr
            op, a = ins.op, ins.args
            # handle branches
            if op == 'j':
                tgt = self.pc_map.get(a[0], None)
                if tgt is not None:
                    self.branch_count += 1
                    self.branch_target = tgt; flush = True
                self.pipe[3] = PipelineReg(ins, 'WB', 0, None)
                comments.append(f"J to {a[0]}")
            elif op in ('beq','bne'):
                r1 = self.regs[self.reg_idx(a[0])]
                r2 = self.regs[self.reg_idx(a[1])]
                take = (r1==r2) if op=='beq' else (r1!=r2)
                if take:
                    tgt = self.pc_map.get(a[2], None)
                    if tgt is not None:
                        self.branch_count += 1
                        self.branch_target = tgt; flush = True
                self.pipe[3] = PipelineReg(ins, 'WB', 0, None)
                comments.append(f"{op.upper()} {'taken' if take else 'not taken'}")
            elif op == 'jal':
                ret = ins.pc + 4
                self.regs[31] = ret
                tgt = self.pc_map.get(a[0], None)
                if tgt is not None:
                    self.branch_count += 1
                    self.branch_target = tgt; flush = True
                self.pipe[3] = PipelineReg(ins, 'WB', 0, None)
                comments.append(f"JAL to {a[0]}, ra={ret}")
            elif op == 'jr':
                addr = self.regs[self.reg_idx(a[0])]
                self.branch_count += 1
                self.branch_target = addr; flush = True
                self.pipe[3] = PipelineReg(ins, 'WB', 0, None)
                comments.append(f"JR to {hex(addr)}")
            # loads/stores
            elif op == 'lw':
                offset, base = int(a[1],0), a[2]
                addr = self.regs[self.reg_idx(base)] + offset
                val = self.mem.get(addr, 0)
                latency = random.randint(self.mem_min, self.mem_max)
                self.pipe[3] = PipelineReg(ins, 'MEM', latency, val)
            elif op == 'sw':
                val = self.regs[self.reg_idx(a[0])]
                offset, base = int(a[1],0), a[2]
                addr = self.regs[self.reg_idx(base)] + offset
                self.mem[addr] = val
                latency = random.randint(self.mem_min, self.mem_max)
                self.pipe[3] = PipelineReg(ins, 'MEM', latency, None)
            # special ops
            elif op == 'li':
                val = int(a[1],0)
                self.pipe[3] = PipelineReg(ins, 'WB', 0, val); comments.append(f"LI {a[0]}={val}")
            elif op == 'move':
                val = self.regs[self.reg_idx(a[1])]
                self.pipe[3] = PipelineReg(ins, 'WB', 0, val); comments.append(f"MOVE {a[0]}={val}")
            else:
                # ALU: add, sub, and, sra, sll, addi, andi
                res = self.exe_alu(ins)
                self.pipe[3] = PipelineReg(ins, 'WB', 0, res)
            # after EX, drop the EX reg
            self.pipe[2] = None
        else:
            self.pipe[2] = self.pipe[1]

        # --- ID stage & hazards ---
        idr = self.pipe[1]
        stall = False
        if idr:
            args = idr.instr.args
            rs = args[1] if len(args)>1 else None
            rt = args[2] if len(args)>2 else None
            prev = self.pipe[2]
            if prev and prev.instr.op=='lw' and prev.instr.args[0] in (rs,rt):
                stall = True; self.stalls_load+=1
                comments.append(f"load-use before {idr.instr.raw}")
        if stall:
            # insert bubble
            self.pipe[2] = None
        else:
            self.pipe[2] = idr
            self.pipe[1] = self.pipe[0]

        # --- IF stage ---
        if not stall:
            if self.pc//4 < len(self.instrs):
                f = self.instrs[self.pc//4]
                self.pipe[1] = PipelineReg(f, 'ID', 0, None)
                next_pc = f.pc + 4
            else:
                self.pipe[1] = None; next_pc = self.pc
        else:
            next_pc = self.pc

        # handle branch flush
        if hasattr(self, 'branch_target'):
            self.pc = self.branch_target
            del self.branch_target
            # squash IF/ID
            self.pipe[1] = None
        else:
            self.pc = next_pc

        # record trace
        for stage, reg in zip(('IF','ID','EX','MEM','WB'), self.pipe):
            if reg: self.trace[reg.instr.pc//4].append(stage)
        print(f"[Cycle {self.cycle:2d}] {'; '.join(comments)}")

    def exe_alu(self, ins):
        r = lambda x: self.regs[self.reg_idx(x)]
        a = ins.args; op = ins.op
        if op=='add': return r(a[1])+r(a[2])
        if op=='sub': return r(a[1])-r(a[2])
        if op=='and': return r(a[1])&r(a[2])
        if op=='sra': return r(a[1])>>int(a[2])
        if op=='sll': return r(a[1])<<int(a[2])
        if op=='addi': return r(a[1])+int(a[2],0)
        if op=='andi': return r(a[1])&int(a[2],0)
        return 0

    def run(self):
        while any(self.pipe) or self.pc//4 < len(self.instrs):
            self.step()
        self.finish()

    def finish(self):
        print("\n=== Pipeline Diagram ===")
        for i, ins in enumerate(self.instrs):
            row = ' | '.join(self.trace[i])
            print(f"{ins.pc:3d}: {ins.raw:<30}: {row}")
        print("\n=== Stats ===")
        print(f"Cycles:         {self.cycle}")
        print(f"Load-use stalls:{self.stalls_load}")
        print(f"MEM stalls:     {self.stalls_mem}")
        print(f"Branches:       {self.branch_count}")
        print(f"Registers:      ")
        for idx,val in enumerate(self.regs): print(f"${idx:02d} = {val}")
        print(f"\nGCD Result ($v0): {self.regs[2]}")

if __name__=='__main__':
    if len(sys.argv)!=2:
        print("Usage: python simulator.py <asm>"); sys.exit(1)
    sim = PipelineSimulator(sys.argv[1])
    sim.run()
