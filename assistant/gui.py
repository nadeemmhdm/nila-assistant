"""Windows desktop setup and model manager; chat UI is supplied by llama.cpp."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import webbrowser
from .core import Manager, CATALOG, prompt


def run():
    root = tk.Tk()
    root.title('Nila Assistant — Setup & Models')
    root.geometry('840x620')
    root.minsize(720, 570)
    manager = Manager()
    events = queue.Queue()
    busy = [False]
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TButton', padding=9)
    style.configure('Title.TLabel', font=('Segoe UI', 23, 'bold'))
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill='both', expand=True)
    title = ttk.Label(frame, text='Your assistant. Your computer.', style='Title.TLabel')
    title.pack(anchor='w')
    ttk.Label(frame,text='Local chat powered by llama.cpp  •  Windows x64  •  CPU mode').pack(anchor='w', pady=(5,20))
    tabs = ttk.Notebook(frame)
    tabs.pack(fill='both',expand=True)
    setup = ttk.Frame(tabs,padding=18)
    models = ttk.Frame(tabs,padding=18)
    settings = ttk.Frame(tabs,padding=18)
    tabs.add(setup,text='  Setup & Chat  ')
    tabs.add(models,text='  Models  ')
    tabs.add(settings,text='  Settings  ')
    status = tk.StringVar(value='Welcome. Give your assistant a name to begin.')
    ttk.Label(frame,textvariable=status,wraplength=770).pack(anchor='w',pady=(14,0))
    controls = []

    def button(parent,text,cmd):
        b=ttk.Button(parent,text=text,command=cmd)
        b.pack(fill='x',pady=4)
        controls.append(b)
        return b

    def refresh():
        installed['values']=manager.installed()
        selected.set(manager.config.get('model',''))
        title.config(text=manager.config['name'] or 'Your assistant. Your computer.')

    def report(s):
        events.put(('status',s))

    def background(fn, done=None):
        if busy[0]:
            return
        busy[0]=True
        manager.cancel.clear()
        for c in controls:
            c.state(['disabled'])
        def work():
            try:
                result=fn()
                events.put(('done',(done,result)))
            except Exception as e:
                events.put(('error',str(e)))
        threading.Thread(target=work,daemon=True).start()

    def tick():
        try:
            while True:
                kind, val=events.get_nowait()
                if kind=='status': status.set(val)
                else:
                    busy[0]=False
                    for c in controls: c.state(['!disabled'])
                    if kind=='error':
                        status.set(val)
                        messagebox.showerror('Local Assistant',val,parent=root)
                    else:
                        done,result=val
                        if done: done(result)
                    refresh()
        except queue.Empty: pass
        root.after(100,tick)

    name=tk.StringVar(value=manager.config['name'])
    ttk.Label(setup,text='1. What would you like to name your AI assistant?').pack(anchor='w')
    ttk.Entry(setup,textvariable=name,font=('Segoe UI',13)).pack(fill='x',pady=7)
    def save_name():
        try:
            manager.config['name']=name.get().strip()
            manager.save()
            refresh()
            status.set('Name saved. It will be used as the default identity in new chats.')
        except Exception as e: messagebox.showerror('Name',str(e),parent=root)
    button(setup,'Save assistant name',save_name)
    button(setup,'2. Install llama.cpp runtime',lambda: background(lambda: manager.install_runtime(report)))
    ttk.Label(setup,text='3. Choose an installed model (add one in the Models tab)').pack(anchor='w',pady=(12,4))
    selected=tk.StringVar(value=manager.config['model'])
    installed=ttk.Combobox(setup,textvariable=selected,state='readonly')
    installed.pack(fill='x',pady=4)
    def prepare():
        manager.config['name']=name.get().strip()
        manager.config['model']=selected.get()
        manager.save()
        manager.selected()
    def web():
        try: prepare()
        except Exception as e:
            messagebox.showerror('Setup',str(e),parent=root)
            return
        background(lambda: manager.start_ui(report),lambda url: webbrowser.open(url))
    def cli():
        try:
            prepare()
            manager.start_cli()
            status.set('CLI chat opened. Close its window or click Unload when finished.')
        except Exception as e: messagebox.showerror('CLI',str(e),parent=root)
    button(setup,'Open Web Chat',web)
    button(setup,'Open CLI Chat',cli)
    button(setup,'Unload model / Stop chat',lambda: background(manager.stop,lambda _:status.set('Model unloaded.')))

    ttk.Label(models,text='Download a starter model or import your own single-file GGUF.').pack(anchor='w')
    catalog=ttk.Combobox(models,values=[x[0] for x in CATALOG],state='readonly')
    catalog.current(0)
    catalog.pack(fill='x',pady=10)
    button(models,'View model card & license',lambda: webbrowser.open(CATALOG[catalog.current()][2]))
    def picked(n):
        manager.config['model']=n
        if manager.config['name']: manager.save()
        status.set('Model added. Select Setup & Chat to start.')
    def get_model(url):
        if not manager.config['name']:
            messagebox.showinfo('Setup','Save your assistant name first.',parent=root)
            return
        if messagebox.askyesno('Download model','Download this GGUF? It may require several GB of storage.\nReview the model card and license before continuing.',parent=root):
            background(lambda: manager.download_model(url,report),picked)
    button(models,'Download selected model',lambda: get_model(CATALOG[catalog.current()][1]))
    def custom():
        url=simpledialog.askstring('Download GGUF','Paste a public HTTPS direct .gguf download URL:',parent=root)
        if url: get_model(url.strip())
    button(models,'Download from GGUF URL…',custom)
    def imp():
        f=filedialog.askopenfilename(filetypes=[('GGUF model','*.gguf')],parent=root)
        if f: background(lambda: manager.import_model(f),picked)
    button(models,'Import existing GGUF…',imp)
    def delete():
        n=selected.get()
        if n and messagebox.askyesno('Delete model',f'Delete the managed copy of {n}?\nYour original imported file is preserved.',parent=root):
            background(lambda: manager.delete_model(n),lambda _:status.set('Model deleted.'))
    button(models,'Delete selected installed model',delete)
    ttk.Label(models,text='Only text chat and single-file GGUF models are supported.\nModel quality, language support and speed depend on the model and your hardware.',wraplength=700).pack(anchor='w',pady=12)

    variables={}
    for key,label in [('threads','CPU threads'),('context','Context tokens'),('port','Local Web UI port')]:
        ttk.Label(settings,text=label).pack(anchor='w',pady=(8,2))
        variables[key]=tk.StringVar(value=str(manager.config[key]))
        ttk.Entry(settings,textvariable=variables[key]).pack(fill='x')
    def save_settings():
        old=manager.config.copy()
        try:
            manager.config.update({k:int(v.get()) for k,v in variables.items()})
            manager.save()
            status.set('Settings saved. Unload and reopen chat to apply.')
        except Exception as e:
            manager.config=old
            messagebox.showerror('Settings',str(e),parent=root)
    button(settings,'Save settings',save_settings)
    def copy_prompt():
        try:
            root.clipboard_clear()
            root.clipboard_append(prompt(manager.config['name']))
            status.set('Identity prompt copied. Paste into Web UI settings if you previously overrode its default.')
        except Exception as e: messagebox.showerror('Identity',str(e),parent=root)
    button(settings,'Copy assistant identity prompt',copy_prompt)
    ttk.Label(settings,text=f'Data and logs: {manager.home}\n\nWeb chat history stays in this browser. Export important chats from the Web UI.\nCLI history is not saved by this launcher.\nAfter changing the name, start a new chat; existing browser settings can override defaults.',wraplength=700).pack(anchor='w',pady=12)
    ttk.Button(frame,text='Cancel current operation',command=manager.cancel.set).pack(anchor='e',pady=(7,0))
    def close():
        if busy[0]:
            manager.cancel.set()
            status.set('Cancelling… wait for the operation to finish, then close again.')
            return
        manager.stop()
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    refresh()
    tick()
    root.mainloop()
