import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import customtkinter as ctk

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

STAGE_COLORS = {
    'IF': "#3498db",
    'ID': "#9b59b6",
    'EX': "#f1c40f",
    'MEM': "#2ecc71",
    'WB': "#e74c3c",
}

STAT_COLORS = {
    'cycles': "#3498db",
    'instructions': "#2ecc71",
    'stalls': "#e74c3c",
    'branches': "#f1c40f",
    'efficiency': "#1abc9c",
    'registers': "#9b59b6",
}

class MIPSPipelineSimulator:
    def __init__(self):
        self.memory = {i: i // 4 for i in range(0, 40, 4)}
        self.registers = [0] * 32
        self.instruction_memory = [
            "addi $t0, $zero, 99",      # Initialize $t0 = 10
            "addi $t1, $zero, 0",      # Initialize $t1 = 20
            "addi $t2, $zero, 0",      # Initialize $t2 = 30
            "loop:",
            "add  $t3, $t0, $t1",       # $t3 = $t0 + $t1
            "add  $t3, $t3, $t2",       # $t3 = $t3 + $t2 (sum)
            "slti $t4, $t3, 100",       # $t4 = 1 if $t3 < 100, else 0
            "beq  $t4, $zero, end",     # Branch to end if sum < 100
            "addi $t0, $t0, 1",         # Increment $t0 by 1
            "addi $t1, $t1, 1",         # Increment $t1 by 1
            "addi $t2, $t2, 1",         # Increment $t2 by 1
            "j    loop",                # Jump back to loop
            "end:",
            "nop"
        ]
        self.filtered_instructions = []
        self.label_to_index = {}
        self.pipeline_log = []
        self.statistics = {}
        self._prepare_instructions()

    def _prepare_instructions(self):
        for line in self.instruction_memory:
            line = line.strip()
            if line.endswith(":"):
                self.label_to_index[line[:-1]] = len(self.filtered_instructions)
            elif line:
                self.filtered_instructions.append(line)

    def _get_reg_num(self, name):
        mapping = {
            '$zero': 0, '$t0': 8, '$t1': 9, '$t2': 10, '$t3': 11,
            '$t4': 12, '$t5': 13, '$t6': 14, '$t7': 15,
            '$s0': 16, '$s1': 17, '$s2': 18, '$s3': 19, '$s4': 20,
            '$a0': 4, '$a1': 5, '$a2': 6, '$a3': 7, '$v0': 2
        }
        return mapping.get(name, 0)

    def _decode(self, instr):
        parts = instr.split()
        op = parts[0]
        if op in ('addi', 'slti'):
            return {'type':'I','opcode':op,
                    'rd':self._get_reg_num(parts[1].strip(',')),
                    'rs':self._get_reg_num(parts[2].strip(',')),
                    'imm':int(parts[3])}
        if op == 'beq':
            return {'type':'I','opcode':'beq',
                    'rs':self._get_reg_num(parts[1].strip(',')),
                    'rt':self._get_reg_num(parts[2].strip(',')),
                    'label':parts[3]}
        if op == 'j':
            return {'type':'J','opcode':'j','label':parts[1]}
        if op in ('lw', 'sw'):
            rt, ob = parts[1].strip(','), parts[2]
            off, base = ob.split('(')
            return {'type':'I','opcode':op,
                    'rt':self._get_reg_num(rt),
                    'base':self._get_reg_num(base.strip(')')),
                    'offset':int(off)}
        if op == 'add':
            return {'type':'R','opcode':'add',
                    'rd':self._get_reg_num(parts[1].strip(',')),
                    'rs':self._get_reg_num(parts[2].strip(',')),
                    'rt':self._get_reg_num(parts[3])}
        if op == 'nop':
            return {'type':'nop','opcode':'nop'}
        raise ValueError(f"Unknown instruction: {instr}")

    def simulate(self):
        PC = 0
        cycle = 0
        total_instructions = 0
        memory_stalls = 0
        delayed_branches = 0
        load_stalls = 0
        wasted_cycles = 0
        inserted_nops = 0
        used_delay_slots = 0
        branch_count = 0

        IF_ID = ID_EX = EX_MEM = MEM_WB = None
        pending_branch = False
        target = 0
        nop_slots = 0
        in_delay_slot = False

        def forward_value(r):
            if MEM_WB:
                ins = MEM_WB['instr']
                if ('rd' in ins and ins['rd']==r and ins['type']=='R') or \
                   ('rt' in ins and ins['rt']==r and ins['opcode']=='lw') or \
                   ('rd' in ins and ins['rd']==r and ins['type']=='I' and ins['opcode'] in ('addi','slti')):
                    return MEM_WB['result']
            if EX_MEM:
                ins = EX_MEM['instr']
                if ('rd' in ins and ins['rd']==r and ins['type']=='R') or \
                   ('rd' in ins and ins['rd']==r and ins['type']=='I' and ins['opcode'] in ('addi','slti')):
                    return EX_MEM['result']
            return self.registers[r]

        self.pipeline_log.clear()

        while True:
            cycle += 1
            stage = {'IF':"--",'ID':"--",'EX':"--",'MEM':"--",'WB':"--"}

            if MEM_WB:
                ins = MEM_WB['instr']
                if 'rd' in ins:
                    self.registers[ins['rd']] = MEM_WB.get('result',0)
                elif 'rt' in ins and ins['opcode']=='lw':
                    self.registers[ins['rt']] = MEM_WB.get('result',0)
                total_instructions += 1
                stage['WB'] = ins['opcode']

            stall = False
            if EX_MEM and EX_MEM['cycles_left']>1:
                EX_MEM['cycles_left'] -= 1
                memory_stalls += 1
                wasted_cycles += 1
                if EX_MEM['instr']['opcode']=='lw':
                    load_stalls += 1
                stall = True
                stage['MEM'] = f"{EX_MEM['instr']['opcode']} ({EX_MEM['cycles_left']})"
            else:
                if EX_MEM:
                    stage['MEM'] = EX_MEM['instr']['opcode']

            if not stall:
                MEM_WB, EX_MEM = EX_MEM, None

                if ID_EX:
                    ins = ID_EX['instr']
                    stage['EX'] = ins['opcode']

                    if in_delay_slot and ins['type']!='nop':
                        used_delay_slots += 1
                        in_delay_slot = False

                    if ins['type']=='R' and ins['opcode']=='add':
                        res = ID_EX['rs_value'] + ID_EX['rt_value']
                        EX_MEM = {'instr':ins,'cycles_left':1,'result':res}
                    elif ins['type']=='I':
                        op = ins['opcode']
                        if op=='addi':
                            res = ID_EX['rs_value'] + ins['imm']
                            EX_MEM = {'instr':ins,'cycles_left':1,'result':res}
                        elif op=='slti':
                            res = 1 if ID_EX['rs_value']<ins['imm'] else 0
                            EX_MEM = {'instr':ins,'cycles_left':1,'result':res}
                        elif op=='beq':
                            if ID_EX['rs_value']==ID_EX['rt_value']:
                                pending_branch = True
                                target = ID_EX['index']+1+ins['offset']
                                delayed_branches += 1
                            branch_count += 1
                            in_delay_slot = True
                            EX_MEM = {'instr':ins,'cycles_left':1}
                        elif op=='lw':
                            addr = ID_EX['base_value']+ins['offset']
                            res = self.memory.get(addr,0)
                            EX_MEM = {'instr':ins,'cycles_left':random.randint(2,3),'result':res}
                        elif op=='sw':
                            addr = ID_EX['base_value']+ins['offset']
                            self.memory[addr] = ID_EX['rt_value']
                            EX_MEM = {'instr':ins,'cycles_left':random.randint(2,3)}
                    elif ins['type']=='J' and ins['opcode']=='j':
                        pending_branch = True
                        target = ins['target']
                        delayed_branches += 1
                        branch_count += 1
                        in_delay_slot = True
                        EX_MEM = {'instr':ins,'cycles_left':1}
                    elif ins['type']=='nop':
                        EX_MEM = {'instr':ins,'cycles_left':1}
                        if in_delay_slot:
                            in_delay_slot = False

                if IF_ID:
                    ins = self._decode(IF_ID['instruction'])
                    rs_val = forward_value(ins.get('rs',0))
                    rt_val = forward_value(ins.get('rt',0))
                    base_val = forward_value(ins.get('base',0)) if 'base' in ins else 0
                    if 'label' in ins:
                        lbl = ins['label']
                        idx = self.label_to_index[lbl]
                        if ins['opcode']=='beq':
                            ins['offset'] = idx - (IF_ID['index']+1)
                        elif ins['opcode']=='j':
                            ins['target'] = idx
                        del ins['label']
                    ID_EX = {'instr':ins,'rs_value':rs_val,'rt_value':rt_val,'base_value':base_val,'index':IF_ID['index']}
                    stage['ID'] = ins['opcode']
                    if ins['opcode'] in ('beq','j'):
                        nop_slots = 4
                else:
                    ID_EX = None

                if PC < len(self.filtered_instructions):
                    if nop_slots>0:
                        IF_ID = {'instruction':'nop','index':-1}
                        stage['IF'] = 'nop'
                        nop_slots -= 1
                        inserted_nops += 1
                    else:
                        IF_ID = {'instruction':self.filtered_instructions[PC],'index':PC}
                        stage['IF'] = self.filtered_instructions[PC].split()[0]
                        if pending_branch:
                            PC, pending_branch = target, False
                        else:
                            PC += 1
                else:
                    IF_ID = None

            self.pipeline_log.append([cycle] + [stage[s] for s in ('IF','ID','EX','MEM','WB')])
            if PC>=len(self.filtered_instructions) and not any((MEM_WB,EX_MEM,ID_EX,IF_ID)):
                break

        eff = (used_delay_slots/branch_count*100) if branch_count>0 else 0
        ipc = total_instructions/cycle if cycle>0 else 0

        self.statistics = {
            'Total Cycles': cycle,
            'Instructions Executed': total_instructions,
            'Memory Stalls': memory_stalls,
            'Load Stalls': load_stalls,
            'Delayed Branches': delayed_branches,
            'Used Delay Slots': used_delay_slots,
            'Branch Instructions': branch_count,
            'Dynamic NOPs': inserted_nops,
            'Wasted Memory Cycles': wasted_cycles,
            'IPC': ipc,
            'Delay Slot Efficiency': eff
        }

        return {'registers': self.registers, 'memory': self.memory}

class PipelineSimulatorGUI:
    def __init__(self, root):
        self.root = root
        root.title("MIPS Pipeline Simulator")
        root.geometry("1100x750")

        self.sim = MIPSPipelineSimulator()
        self.current_cycle = 0
        self.speed = 500
        self.playing = False

        self._build_layout()
        self._disable_controls()

    def _build_layout(self):
        self.left = ctk.CTkFrame(self.root, width=1500)
        self.left.pack(side="left", fill="both", padx=10, pady=10)

        self.right_frame = ctk.CTkFrame(self.root)  # outer frame to hold the scrollbar
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.right = ctk.CTkScrollableFrame(self.right_frame)
        self.right.pack(fill="both", expand=True)

        ctk.CTkLabel(self.left, text="MIPS Pipeline Execution", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        self._make_pipeline_header()
        self.table = ctk.CTkScrollableFrame(self.left)
        self.table.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(self.right, text="Performance Statistics", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        self.stats_frame = ctk.CTkFrame(self.right)
        self.stats_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(self.right, text="Simulation Controls", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20,10))
        controls = ctk.CTkFrame(self.right)
        controls.pack(fill="x", pady=5)
        ctk.CTkButton(controls, text="Run Simulation", command=self.run).grid(row=0, column=0, padx=5, pady=5)
        ctk.CTkButton(controls, text="Reset", fg_color="#e74c3c", hover_color="#c0392b", command=self.reset).grid(row=0, column=1, padx=5, pady=5)

        anim = ctk.CTkFrame(self.right)
        anim.pack(fill="x", pady=5)
        ctk.CTkLabel(anim, text="Speed:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.slider = ctk.CTkSlider(anim, from_=100, to=2000, number_of_steps=19, command=self._set_speed)
        self.slider.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.slider.set(500)
        self.play_btn = ctk.CTkButton(anim, text="▶ Play", command=self.toggle)
        self.play_btn.grid(row=1, column=0, padx=5, pady=5)
        self.next_btn = ctk.CTkButton(anim, text="Next →", command=self.next)
        self.next_btn.grid(row=1, column=1, padx=5, pady=5)
        self.cycle_label = ctk.CTkLabel(anim, text="Cycle: 0/0")
        self.cycle_label.grid(row=2, column=0, columnspan=2, pady=5)

        ctk.CTkButton(self.right, text="Show Charts", command=self.show_charts).pack(pady=10, fill="x")
        ctk.CTkLabel(self.right, text="Final State", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20,10))

        tabs = ctk.CTkTabview(self.right)
        tabs.pack(fill="both", expand=True, pady=10)
        self.reg_tab = tabs.add("Registers")
        self.mem_tab = tabs.add("Memory")
        self.reg_frame = ctk.CTkScrollableFrame(self.reg_tab)
        self.reg_frame.pack(fill="both", expand=True)
        self.mem_frame = ctk.CTkScrollableFrame(self.mem_tab)
        self.mem_frame.pack(fill="both", expand=True)
        
    def _make_pipeline_header(self):
        frame = ctk.CTkFrame(self.left)
        frame.pack(fill="x", padx=5, pady=(5,0))
        headers = ["Cycle","IF","ID","EX","MEM","WB"]
        for i, h in enumerate(headers):
            color = STAGE_COLORS.get(h) if i>0 else "transparent"
            lbl = ctk.CTkLabel(frame, text=h, width=80, fg_color=color if color else "transparent", corner_radius=6, font=ctk.CTkFont(weight="bold"))
            lbl.grid(row=0, column=i, padx=2, pady=2)
            frame.grid_columnconfigure(i, weight=1)

    def _update_table(self):
        for w in self.table.winfo_children():
            w.destroy()
        for idx, entry in enumerate(self.sim.pipeline_log):
            row = ctk.CTkFrame(self.table)
            row.pack(fill="x", pady=1)
            bg = "#e0e0e0" if idx==self.current_cycle else None
            ctk.CTkLabel(row, text=str(entry[0]), width=80, fg_color=bg).grid(row=0, column=0, padx=2)
            for j, val in enumerate(entry[1:]):
                col = ['IF','ID','EX','MEM','WB'][j]
                color = STAGE_COLORS[col] if val!="--" else "transparent"
                ctk.CTkLabel(row, text=val, width=80, fg_color=color, corner_radius=6).grid(row=0, column=j+1, padx=2)
            for k in range(6):
                row.grid_columnconfigure(k, weight=1)

    def _update_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        for r, v in self.sim.statistics.items():
            text = f"{v:.2f}%" if r in ("IPC","Delay Slot Efficiency") else str(v)
            ctk.CTkLabel(self.stats_frame, text=f"{r}:").grid(row=list(self.sim.statistics).index(r), column=0, sticky="w", padx=5)
            ctk.CTkLabel(self.stats_frame, text=text).grid(row=list(self.sim.statistics).index(r), column=1, sticky="e", padx=5)

    def _update_final(self, state):
        for w in self.reg_frame.winfo_children():
            w.destroy()
        for w in self.mem_frame.winfo_children():
            w.destroy()
        names = {0:"$zero",2:"$v0",4:"$a0",5:"$a1",6:"$a2",7:"$a3",8:"$t0",9:"$t1",10:"$t2",11:"$t3",12:"$t4",13:"$t5",14:"$t6",15:"$t7",16:"$s0",17:"$s1",18:"$s2",19:"$s3",20:"$s4"}
        for i, val in enumerate(state['registers']):
            if i in names and val!=0:
                f = ctk.CTkFrame(self.reg_frame); f.pack(fill="x", pady=1)
                ctk.CTkLabel(f, text=f"{names[i]} (reg {i}):", width=120).grid(row=0, column=0, sticky="w", padx=5)
                ctk.CTkLabel(f, text=str(val), width=60).grid(row=0, column=1, sticky="e", padx=5)
        for addr in sorted(state['memory']):
            if addr<=40:
                f = ctk.CTkFrame(self.mem_frame); f.pack(fill="x", pady=1)
                ctk.CTkLabel(f, text=f"Address {addr:2d}:", width=120).grid(row=0, column=0, sticky="w", padx=5)
                ctk.CTkLabel(f, text=str(state['memory'][addr]), width=60).grid(row=0, column=1, sticky="e", padx=5)

    def run(self):
        final = self.sim.simulate()
        self._update_stats()
        self._update_final(final)
        self.current_cycle = 0
        self._update_table()
        self.cycle_label.configure(text=f"Cycle: 1/{len(self.sim.pipeline_log)}")
        self._enable_controls()

    def reset(self):
        self.sim = MIPSPipelineSimulator()
        for frame in (self.table, self.stats_frame, self.reg_frame, self.mem_frame):
            for w in frame.winfo_children():
                w.destroy()
        self.current_cycle = 0
        self.playing = False
        self.cycle_label.configure(text="Cycle: 0/0")

    def _set_speed(self, val):
        self.speed = int(val)

    def toggle(self):
        self.playing = not self.playing
        self.play_btn.configure(text="⏸ Pause" if self.playing else "▶ Play")
        if self.playing:
            self._animate()

    def _animate(self):
        if not self.playing:
            return
        if self.current_cycle < len(self.sim.pipeline_log) - 1:
            self.current_cycle += 1
            self._update_table()
            self.cycle_label.configure(text=f"Cycle: {self.current_cycle+1}/{len(self.sim.pipeline_log)}")
            self.root.after(self.speed, self._animate)
        else:
            self.playing = False
            self.play_btn.configure(text="▶ Play")

    def next(self):
        if self.current_cycle < len(self.sim.pipeline_log) - 1:
            self.current_cycle += 1
            self._update_table()
            self.cycle_label.configure(text=f"Cycle: {self.current_cycle+1}/{len(self.sim.pipeline_log)}")

    def _enable_controls(self):
        for w in (self.play_btn, self.next_btn, self.slider):
            w.configure(state="normal")
        self.show_btn.configure(state="normal")

    def _disable_controls(self):
        for w in (self.play_btn, self.next_btn, self.slider):
            w.configure(state="disabled")
        self.show_btn = None

    def show_charts(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Pipeline Charts")
        win.geometry("900x600")
        tabs = ctk.CTkTabview(win)
        tabs.pack(fill="both", expand=True, padx=10, pady=10)
        exec_tab = tabs.add("Execution")
        eff_tab = tabs.add("Efficiency")
        stall_tab = tabs.add("Stalls")
        self._chart_execution(exec_tab)
        self._chart_efficiency(eff_tab)
        self._chart_stalls(stall_tab)

    def _chart_execution(self, parent):
        fig, ax = plt.subplots(figsize=(8,5))
        stats = self.sim.statistics
        cats = ['Executed','Branches','Delayed','NOPs']
        vals = [stats['Instructions Executed'], stats['Branch Instructions'], stats['Delayed Branches'], stats['Dynamic NOPs']]
        cols = [STAT_COLORS['instructions'], STAT_COLORS['branches'], STAT_COLORS['branches'], STAT_COLORS['stalls']]
        bars = ax.bar(cats, vals, color=cols)
        ax.set_ylabel('Count')
        ax.set_title('Instruction Profile')
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x()+b.get_width()/2, h+0.1, f'{int(h)}', ha='center')
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _chart_efficiency(self, parent):
        fig, (a1, a2) = plt.subplots(1,2,figsize=(8,5))
        stats = self.sim.statistics
        total = stats['Total Cycles']
        used = total - stats['Memory Stalls'] - stats['Dynamic NOPs']
        labels = ['Exec','Stalls','NOPs']
        sizes = [used, stats['Memory Stalls'], stats['Dynamic NOPs']]
        cols = [STAT_COLORS['cycles'], STAT_COLORS['stalls'], STAT_COLORS['efficiency']]
        a1.pie(sizes, labels=labels, colors=cols, autopct='%1.1f%%', startangle=90)
        a1.axis('equal')
        a1.set_title('Cycle Use')
        ipc = stats['IPC']
        a2.bar(['IPC'], [ipc], color=STAT_COLORS['instructions'])
        a2.set_ylim(0, max(1.0, ipc*1.2))
        a2.set_title('IPC')
        a2.text(0, ipc+0.05, f'{ipc:.2f}', ha='center')
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _chart_stalls(self, parent):
        fig, ax = plt.subplots(figsize=(8,5))
        stats = self.sim.statistics
        cats = ['Mem Stalls','Load Stalls','Wasted Cycles']
        vals = [stats['Memory Stalls'], stats['Load Stalls'], stats['Wasted Memory Cycles']]
        cols = [STAT_COLORS['stalls'], STAT_COLORS['registers'], STAT_COLORS['efficiency']]
        bars = ax.bar(cats, vals, color=cols)
        ax.set_ylabel('Count')
        ax.set_title('Stalls Analysis')
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x()+b.get_width()/2, h+0.1, f'{int(h)}', ha='center')
        ax.text(0.5, -0.2,
                f"Delay Slots: {stats['Used Delay Slots']}/{stats['Branch Instructions']} ({stats['Delay Slot Efficiency']:.1f}%)",
                transform=ax.transAxes, ha='center')
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

if __name__ == "__main__":
    app = ctk.CTk()
    PipelineSimulatorGUI(app)
    app.mainloop()