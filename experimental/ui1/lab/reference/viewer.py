"""Windows viewer for the actual ARM P401 GUI plus native network replay."""
from pathlib import Path
import json, queue, struct, subprocess, threading, time, tkinter as tk, sys
from tkinter import ttk, messagebox
from capture_screen import png_from_bgra
from design_tab import DesignTab

WORK = Path(__file__).resolve().parent
WS = WORK.parents[1]
RUNTIME = WORK / 'runtime'
RUNTIME.mkdir(exist_ok=True)
WSL_WS = '/opt/p401-workspace'
NO_WINDOW = subprocess.CREATE_NO_WINDOW

class Viewer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('P401 PC Lab â€” firmware and menu designs')
        self.root.resizable(False, False)
        self.closed = False
        self.messages = queue.Queue()
        self.photo = None
        self.last_frame = None
        self.process = None
        self.replay_process = None
        self.last_drag = 0.0
        self.lock = None
        try:
            import msvcrt
            self.lock = (RUNTIME / 'viewer.lock').open('a+b')
            self.lock.seek(0)
            if not self.lock.read(1):
                self.lock.write(b'0'); self.lock.flush()
            self.lock.seek(0)
            msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            messagebox.showinfo('P401 PC Lab', 'The P401 viewer is already running.')
            self.root.destroy()
            return
        ttk.Label(self.root, text='Original P401 software Â· virtual screen and mouse Â· physical hardware absent', padding=(12, 8)).pack(anchor='w')
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill='both', expand=True, padx=8)
        ui = ttk.Frame(self.tabs)
        self.tabs.add(ui, text='P401 menus')
        self.canvas = tk.Canvas(ui, width=800, height=480, background='black', highlightthickness=0)
        self.canvas.pack()
        self.canvas.create_text(400, 240, text='Starting the original ARM interfaceâ€¦', fill='white', tags='starting', font=('Segoe UI', 14))
        self.image_id = self.canvas.create_image(0, 0, anchor='nw')
        self.canvas.bind('<ButtonPress-1>', lambda e: self.pointer(e.x, e.y, 1))
        self.canvas.bind('<ButtonRelease-1>', lambda e: self.pointer(e.x, e.y, 0))
        self.canvas.bind('<B1-Motion>', self.drag)
        ttk.Label(ui, text='Click to touch. Drag horizontally to change launcher pages. Changes stay in the PC copy.', padding=8).pack(anchor='w')
        replay = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(replay, text='Original vs W3 connection test')
        ttk.Label(replay, text='Native CarPlay control replay', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(replay, text='Uses your recorded phone announcement and a synthetic HTTP endpoint.\nTests the real ARM client; does not emulate an iPhone, MFi, radio or media streaming.', padding=(0, 6)).pack(anchor='w')
        self.run_button = ttk.Button(replay, text='Run original and W3 now', command=self.run_replay)
        self.run_button.pack(anchor='w', pady=(0, 8))
        self.replay_label = ttk.Label(replay, text='Saved W3 result below. Press Run for a fresh execution.')
        self.replay_label.pack(anchor='w', pady=(0, 8))
        self.outcomes = ttk.Label(replay, text='', font=('Segoe UI', 10, 'bold'))
        self.outcomes.pack(anchor='w', pady=(0, 8))
        self.results = tk.Text(replay, width=96, height=21, wrap='word', font=('Consolas', 9), background='#ffffff')
        self.results.pack(fill='both', expand=True)
        self.show_result(WS / 'work/network_repair/evidence/ipv6-only', 'Saved verified replay')
        self.design_tab=DesignTab(self.tabs,WS,WSL_WS)
        self.tabs.bind('<<NotebookTabChanged>>',self.tab_changed)
        if '--designs' in sys.argv:self.tabs.select(self.design_tab.frame)
        self.status = ttk.Label(self.root, text='Starting isolated GUIâ€¦', padding=(12, 8))
        self.status.pack(anchor='w')
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        (RUNTIME / 'input.bin').write_bytes(b'')
        (RUNTIME / 'stop').unlink(missing_ok=True)
        (RUNTIME / 'frame.bgra').unlink(missing_ok=True)
        self.log = (RUNTIME / 'launcher.log').open('w')
        self.process = subprocess.Popen(['wsl', '-d', 'Codex-P401-Build', '-u', 'root', '--',
            'unshare', '-m', '-n', '-p', '-i', '-f', 'python3',
            WSL_WS + '/work/visual_emulator/boot_probe.py', '--live'],
            stdout=self.log, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        self.root.after(150, self.tick)
        self.root.mainloop()

    def tab_changed(self,event):
        if self.tabs.select()==str(self.design_tab.frame):self.design_tab.start()

    def pointer(self, x, y, buttons):
        if self.closed:
            return
        # Always deliver release, even when a drag finishes outside the screen.
        x, y = min(799, max(0, x)), min(479, max(0, y))
        with (RUNTIME / 'input.bin').open('ab', buffering=0) as f:
            f.write(struct.pack('<iii', x, y, buttons))

    def drag(self, event):
        now = time.monotonic()
        if now - self.last_drag >= .04:
            self.pointer(event.x, event.y, 1)
            self.last_drag = now

    def tick(self):
        if self.closed:
            return
        try:
            data = (RUNTIME / 'frame.bgra').read_bytes()
            if len(data) == 800 * 480 * 4 and data != self.last_frame:
                self.photo = tk.PhotoImage(data=png_from_bgra(data))
                self.canvas.itemconfigure(self.image_id, image=self.photo)
                self.canvas.delete('starting')
                self.last_frame = data
                self.status.config(text='Native menus running. Wi-Fi, Bluetooth, MCU, authentication hardware and CarPlay video are absent.')
        except (OSError, tk.TclError):
            pass
        if self.process and self.process.poll() is not None:
            self.status.config(text='GUI stopped. See work/visual_emulator/runtime/launcher.log for details.')
        while not self.messages.empty():
            success, payload = self.messages.get_nowait()
            self.run_button.config(state='normal')
            if success:
                self.show_result(payload, 'Fresh execution completed')
                self.replay_label.config(text='Fresh result: original timed out; W3 completed the synthetic control request.' if self.last_replay_passed else 'Fresh execution differed from the expected result â€” inspect the output below.')
            else:
                self.replay_label.config(text='Replay did not complete.')
                self.results.config(state='normal'); self.results.delete('1.0', 'end')
                self.results.insert('end', payload); self.results.config(state='disabled')
        self.root.after(150, self.tick)

    def show_result(self, directory, heading):
        self.last_replay_passed = False
        try:
            data = json.loads((directory / 'NATIVE_REPLAY_RESULTS.json').read_text())
            rows = data['results']
            self.last_replay_passed = len(rows) == 2 and rows[0]['exit_code'] == 1 and rows[1]['exit_code'] == 0 and 'status=-6722' in rows[0]['output'] and 'status=0' in rows[1]['output']
            self.outcomes.config(text=('Original: TIMEOUT\nW3: CONTROL REQUEST ACCEPTED (synthetic endpoint)' if self.last_replay_passed else 'Outcome differs from the expected comparison; inspect the trace.'))
            text = heading + '\n\n'
            for row in rows:
                label = 'ORIGINAL' if row['case'] == 'native_original' else 'W3 PATCH'
                text += f"{label} â€” {row['seconds']:.3f} seconds\n{row['output']}\n"
            text += '\nSYNTHETIC ENDPOINT RECEIVED\n' + (directory / 'peer.txt').read_text()
            text += '\nScope: this replay tests the control request, not a complete wireless CarPlay session.\n'
        except (OSError, ValueError, KeyError) as e:
            text = 'No saved result available: ' + str(e)
        self.results.config(state='normal'); self.results.delete('1.0', 'end')
        self.results.insert('end', text); self.results.config(state='disabled')

    def run_replay(self):
        self.run_button.config(state='disabled')
        self.replay_label.config(text='Running the original ARM client, then W3, in an isolated networkâ€¦')
        self.outcomes.config(text='Executingâ€¦')
        def task():
            scenario = 'visual-' + time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns() % 1000000)
            try:
                self.replay_process = subprocess.Popen(['wsl', '-d', 'Codex-P401-Build', '-u', 'root', '--',
                    'env', 'NATIVE_TEST=1', 'TEST_SCENARIO=' + scenario,
                    'unshare', '-n', '-m', 'python3', WSL_WS + '/work/network_repair/connect_lab.py'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
                output, _ = self.replay_process.communicate(timeout=75)
                if self.replay_process.returncode:
                    raise RuntimeError(output.decode(errors='replace'))
                self.messages.put((True, WS / 'work/network_repair/evidence' / scenario))
            except Exception as e:
                self.messages.put((False, str(e)))
        threading.Thread(target=task, daemon=True).start()

    def close(self):
        self.closed = True
        self.design_tab.close()
        (RUNTIME / 'stop').touch()
        self.root.destroy()
        if self.process:
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.terminate()
        self.log.close()
        if self.lock:
            self.lock.close()

if __name__ == '__main__':
    Viewer()
