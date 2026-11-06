"""Viewer controls for native ARM design previews, isolated from the stock lab."""
from pathlib import Path
import subprocess, struct, tkinter as tk, time
from tkinter import ttk
from capture_screen import png_from_bgra

class DesignTab:
    def __init__(self, notebook, ws, wsl_ws):
        self.ws, self.wsl_ws=ws,wsl_ws
        self.runtime=ws/'work/ui_customization/runtime'
        self.runtime.mkdir(exist_ok=True)
        self.frame=ttk.Frame(notebook)
        notebook.add(self.frame,text='Jaguar menu')
        row=ttk.Frame(self.frame,padding=(8,6));row.pack(fill='x')
        self.choice=tk.IntVar(value=3)
        for i,label in [(3,'XFR Â· native menu'),(0,'Classic preview'),(1,'XFR preview'),(2,'Touring preview')]:
            ttk.Radiobutton(row,text=label,variable=self.choice,value=i,command=self.choose).pack(side='left',padx=(0,14))
        self.canvas=tk.Canvas(self.frame,width=800,height=480,background='black',highlightthickness=0)
        self.canvas.pack()
        self.waiting=self.canvas.create_text(400,240,text='Select this tab to start the native ARM previews.',fill='white',font=('Segoe UI',13))
        self.img=self.canvas.create_image(0,0,anchor='nw');self.photo=None;self.last=None
        self.canvas.bind('<ButtonPress-1>',lambda e:self.pointer(e.x,e.y,1))
        self.canvas.bind('<ButtonRelease-1>',lambda e:self.pointer(e.x,e.y,0))
        self.note=ttk.Label(self.frame,text='Native applications and name editor. Changes stay in the PC copy; physical radio and reboot are absent.',padding=(8,6));self.note.pack(anchor='w')
        self.status=ttk.Label(self.frame,text='Nothing is installed on the box or USB.',padding=(8,3));self.status.pack(anchor='w')
        self.process=None;self.log=None;self.closed=False;self.native_running=None
        self.frame.after(200,self.tick)
    def choose(self):
        choice=self.choice.get()
        if choice<3:(self.runtime/'design.txt').write_text(str(choice))
        self.note.config(text=('Native applications and name editor. Changes stay in the PC copy; physical radio and reboot are absent.' if choice==3 else 'Design preview: app screens are placeholders. Select XFR Â· native menu to try the actual integration.'))
        if self.process is not None and (choice==3)!=self.native_running:
            (self.runtime/'stop').touch()
            try:self.process.wait(timeout=6)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=3)
            self.process=None
            if self.log:self.log.close()
            self.start()
    def start(self):
        if self.process is not None:return
        self.choose();(self.runtime/'stop').unlink(missing_ok=True)
        (self.runtime/'input.bin').write_bytes(b'')
        (self.runtime/'frame.bgra').unlink(missing_ok=True)
        self.log=(self.runtime/'launcher.log').open('w')
        self.native_running=self.choice.get()==3
        flags=['--settings-preview','--native-layout'] if self.native_running else ['--designs']
        self.process=subprocess.Popen(['wsl','-d','Codex-P401-Build','-u','root','--','unshare','-m','-n','-p','-i','-f','python3',self.wsl_ws+'/work/visual_emulator/boot_probe.py',*flags,'--live'],stdout=self.log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        self.status.config(text='Starting the isolated ARM previewâ€¦')
    def pointer(self,x,y,buttons):
        if self.closed or self.process is None:return
        with (self.runtime/'input.bin').open('ab',buffering=0) as f:f.write(struct.pack('<iii',min(799,max(0,x)),min(479,max(0,y)),buttons))
    def tick(self):
        if self.closed:return
        try:
            data=(self.runtime/'frame.bgra').read_bytes()
            if len(data)==800*480*4 and data!=self.last:
                self.photo=tk.PhotoImage(data=png_from_bgra(data));self.canvas.itemconfigure(self.img,image=self.photo)
                self.canvas.delete(self.waiting);self.last=data
                self.status.config(text='Native ARM/Qt preview Â· saved names stay in this simulator copy.')
        except (OSError,tk.TclError):pass
        if self.process is not None and self.process.poll() is not None:self.status.config(text='Preview stopped. Close and reopen the lab to restart it.')
        self.frame.after(150,self.tick)
    def close(self):
        self.closed=True
        if self.process is not None:
            (self.runtime/'stop').touch()
            try:self.process.wait(timeout=6)
            except subprocess.TimeoutExpired:self.process.terminate()
        if self.log:self.log.close()
