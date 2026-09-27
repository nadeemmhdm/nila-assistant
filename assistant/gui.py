"""Desktop management, streaming chat, memory and speech controls."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
import webbrowser
from .core import Manager, CATALOG
from .memory import Memory
from .chat import Chat
from .speech import Voices, Speaker, VOICES


def run():
    root=tk.Tk(); root.title('Nila Assistant — Local Chat'); root.geometry('940x760'); root.minsize(840,690)
    m=Manager()
    try: memory=Memory(m.home,m.config)
    except Exception as e:
        if not messagebox.askyesno('Saved memory unavailable',str(e)+'\n\nDelete the unreadable saved memory and start fresh?',parent=root):
            root.destroy(); return
        (m.home/'memory.dpapi').unlink(missing_ok=True); memory=Memory(m.home,m.config)
    chat=Chat(m,memory); voices=Voices(m)
    events=queue.Queue(); busy=[False]; generating=[False]
    def report(text): events.put(('status',text))
    speaker=Speaker(m,report)
    style=ttk.Style(); style.theme_use('clam'); style.configure('TButton',padding=7)
    frame=ttk.Frame(root,padding=18); frame.pack(fill='both',expand=True)
    title=ttk.Label(frame,text='Nila Assistant',font=('Segoe UI',23,'bold')); title.pack(anchor='w')
    ttk.Label(frame,text='Local models • Private memory • Streaming speech').pack(anchor='w',pady=(2,12))
    tabs=ttk.Notebook(frame); tabs.pack(fill='both',expand=True)
    pages={}
    for name in ['Setup','Chat','Models','Memory','Voice','Settings']:
        pages[name]=ttk.Frame(tabs,padding=15); tabs.add(pages[name],text='  '+name+'  ')
    status=tk.StringVar(value='Name your assistant, install runtime, and add a model to begin.')
    ttk.Label(frame,textvariable=status,wraplength=880).pack(anchor='w',pady=(10,0))
    controls=[]
    def button(parent,text,fn):
        widget=ttk.Button(parent,text=text,command=fn); widget.pack(fill='x',pady=3); controls.append(widget); return widget
    def guarded(fn):
        def wrapped():
            try: return fn()
            except Exception as e: messagebox.showerror('Nila Assistant',str(e),parent=root)
        return wrapped
    def background(fn,done=None):
        if busy[0]: return
        busy[0]=True; m.cancel.clear()
        for w in controls: w.state(['disabled'])
        def work():
            try: events.put(('done',(done,fn())))
            except Exception as e: events.put(('error',str(e)))
        threading.Thread(target=work,daemon=True).start()
    def refresh():
        installed['values']=m.installed(); selected.set(m.config['model'])
        title.config(text=(m.config['name']+' · Nila Assistant') if m.config['name'] else 'Nila Assistant')
        facts.delete(0,'end')
        for fact in memory.facts: facts.insert('end',fact)
        memory_status.set(f'{len(memory.turns)} stored exchanges · {len(memory.facts)} facts · '+
                          ('Encrypted persistence ON' if m.config['persist_memory'] else 'Session only; closes without saving'))
        voice_status.set('Downloaded: '+(', '.join(voices.installed()) or 'none'))
    def tick():
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='status': status.set(value)
                elif kind=='token':
                    transcript.config(state='normal'); transcript.insert('end',value); transcript.see('end'); transcript.config(state='disabled')
                else:
                    busy[0]=False; generating[0]=False
                    for w in controls: w.state(['!disabled'])
                    if kind=='error': status.set(value); messagebox.showerror('Nila Assistant',value,parent=root)
                    else:
                        callback,result=value
                        if callback:
                            try: callback(result)
                            except Exception as e: messagebox.showerror('Nila Assistant',str(e),parent=root)
                    refresh()
        except queue.Empty: pass
        root.after(75,tick)

    setup=pages['Setup']; assistant_name=tk.StringVar(value=m.config['name'])
    ttk.Label(setup,text='1. What would you like to name your assistant?').pack(anchor='w')
    ttk.Entry(setup,textvariable=assistant_name,font=('Segoe UI',14)).pack(fill='x',pady=6)
    def save_name():
        if m.running(): raise ValueError('Unload the model before changing its name.')
        m.config['name']=assistant_name.get().strip(); m.save(); refresh(); status.set('Assistant name saved.')
    button(setup,'Save name',guarded(save_name))
    button(setup,'2. Install llama.cpp runtime',lambda: background(lambda:m.install_runtime(report)))
    ttk.Label(setup,text='3. Add a model in Models, then choose it here:').pack(anchor='w',pady=(12,3))
    selected=tk.StringVar(value=m.config['model'])
    installed=ttk.Combobox(setup,textvariable=selected,state='readonly'); installed.pack(fill='x',pady=5)
    def prepare():
        if m.running(): raise ValueError('Unload the active model before loading another.')
        m.config['name']=assistant_name.get().strip(); m.config['model']=selected.get(); m.save(); m.selected()
    def load(native=False):
        prepare()
        def loaded(url):
            status.set('Loaded. Use Chat, or open the native Web UI.')
            if native:
                messagebox.showinfo('Native Web UI','Paste the session API key into the Web UI API-key setting.\nUse the Copy session key button. Native browser history is not DPAPI encrypted.',parent=root)
                webbrowser.open(url)
            else: tabs.select(pages['Chat'])
        background(lambda:m.start_ui(report),loaded)
    button(setup,'Load model → Nila Chat',guarded(load))
    button(setup,'Load model → native Web UI',guarded(lambda:load(True)))
    def key():
        if not m.api_key: raise ValueError('Load a model first.')
        root.clipboard_clear(); root.clipboard_append(m.api_key)
        status.set('Session key copied. Keep it private; it changes on the next load.')
    button(setup,'Copy session API key (native Web UI only)',guarded(key))
    def unload():
        speaker.close(); m.stop(); status.set('Model unloaded.')
    button(setup,'Unload model',lambda:background(unload))
    ttk.Label(setup,text='One model stays loaded until Unload or exit. Native Web UI is available at the configured localhost port.\nMemory and auto-speak are managed by Nila Chat, not the native browser UI.',wraplength=840).pack(anchor='w',pady=10)

    cp=pages['Chat']; transcript=scrolledtext.ScrolledText(cp,wrap='word',state='disabled',height=19,font=('Segoe UI',11))
    transcript.pack(fill='both',expand=True)
    def display(text):
        transcript.config(state='normal'); transcript.insert('end',text); transcript.see('end'); transcript.config(state='disabled')
    for u,a in memory.turns: display(f'You: {u}\n\n{m.config["name"]}: {a}\n\n')
    entry=tk.Text(cp,height=3,wrap='word',font=('Segoe UI',11)); entry.pack(fill='x',pady=8)
    def send():
        user=entry.get('1.0','end').strip()
        if not user: return
        if not m.running(): raise ValueError('Load a model in Setup first.')
        if m.config['auto_speak']:
            speaker.close(); speaker.start()
        entry.delete('1.0','end'); display('\nYou: '+user+'\n\n'+m.config['name']+': ')
        generating[0]=True
        def work():
            try: return chat.stream(user,lambda text:events.put(('token',text)),speaker.enqueue if m.config['auto_speak'] else None)
            except Exception:
                speaker.stop(); raise
        def done(_):
            display('\n\n'); timing=chat.last_stats
            first=timing.get('first_token_seconds')
            status.set(f'Reply complete. First text: {first:.2f}s. '+f'Context used: {timing["input_tokens"]} tokens.' if first is not None else 'Reply complete.')
        background(work,done)
    button(cp,'Send',guarded(send))
    def new_chat():
        speaker.close(); memory.clear(facts=False)
        transcript.config(state='normal'); transcript.delete('1.0','end'); transcript.config(state='disabled'); refresh()
    button(cp,'New chat (keep saved facts)',guarded(new_chat))
    ttk.Button(cp,text='Stop generation + speech (unloads model)',command=lambda:cancel(True)).pack(fill='x',pady=3)
    ttk.Button(cp,text='Stop speech only',command=speaker.stop).pack(fill='x',pady=3)

    mp=pages['Models']; ttk.Label(mp,text='Starter models or your own single-file GGUF.').pack(anchor='w')
    catalog=ttk.Combobox(mp,values=[x[0] for x in CATALOG],state='readonly'); catalog.current(0); catalog.pack(fill='x',pady=8)
    button(mp,'View model card / license',lambda:webbrowser.open(CATALOG[catalog.current()][2]))
    def picked(name):
        m.config['model']=name
        if m.config['name']: m.save()
        status.set('Model installed. Select it in Setup and click Load.')
    def get_model(url):
        if m.running(): raise ValueError('Unload the model before modifying model storage.')
        if messagebox.askyesno('Download model','Download this GGUF? Review its model card/license first. Large models can exceed your RAM.',parent=root):
            background(lambda:m.download_model(url,report),picked)
    button(mp,'Download selected model',guarded(lambda:get_model(CATALOG[catalog.current()][1])))
    def custom():
        url=simpledialog.askstring('GGUF URL','Public HTTPS direct .gguf URL:',parent=root)
        if url: get_model(url.strip())
    button(mp,'Download GGUF URL…',guarded(custom))
    def imp():
        if m.running(): raise ValueError('Unload the model first.')
        file=filedialog.askopenfilename(filetypes=[('GGUF model','*.gguf')],parent=root)
        if file: background(lambda:m.import_model(file),picked)
    button(mp,'Import GGUF file…',guarded(imp))
    def delete():
        if selected.get() and messagebox.askyesno('Delete model','Delete selected managed model? Your original imported file stays intact.',parent=root):
            background(lambda:m.delete_model(selected.get()))
    button(mp,'Delete selected installed model',guarded(delete))

    mem=pages['Memory']; memory_status=tk.StringVar(); ttk.Label(mem,textvariable=memory_status,wraplength=830).pack(anchor='w',pady=5)
    ttk.Label(mem,text='Explicit saved facts are included in future Nila Chat prompts. Review what you save.').pack(anchor='w')
    facts=tk.Listbox(mem,height=13); facts.pack(fill='both',expand=True,pady=8)
    def remember():
        text=simpledialog.askstring('Remember a fact','What should your assistant remember? (500 characters max)',parent=root)
        if text: memory.remember(text); refresh()
    def forget():
        indices=facts.curselection()
        if indices: memory.forget(indices[0]); refresh()
    button(mem,'Add memory fact…',guarded(remember)); button(mem,'Forget selected fact',guarded(forget))
    def clear():
        if messagebox.askyesno('Clear memory','Delete saved facts and chat history from Nila memory? Browser chats and backups are separate.',parent=root):
            memory.clear(); transcript.config(state='normal'); transcript.delete('1.0','end'); transcript.config(state='disabled'); refresh()
    button(mem,'Clear all Nila memory',guarded(clear))
    ttk.Label(mem,text='Persistence is OFF by default. Enable it in Settings to save encrypted memory.\nEncryption is tied to your Windows account. It does not protect against malware running as you.',wraplength=830).pack(anchor='w',pady=6)

    vp=pages['Voice']; voice_id=tk.StringVar(value=m.config['voice'])
    ttk.Label(vp,text='Offline speech — choose a voice matching your response language.').pack(anchor='w')
    voice_combo=ttk.Combobox(vp,values=list(VOICES),textvariable=voice_id,state='readonly'); voice_combo.pack(fill='x',pady=8)
    voice_status=tk.StringVar(); ttk.Label(vp,textvariable=voice_status,wraplength=830).pack(anchor='w')
    button(vp,'Read selected voice card / license',lambda:webbrowser.open('https://huggingface.co/rhasspy/piper-voices/blob/main/'+VOICES[voice_id.get()][1]+'/MODEL_CARD'))
    def engine():
        if messagebox.askyesno('Install speech engine','Install optional GPL-licensed Piper 1.8.0 and dependencies from PyPI? Python 3.12 may also be installed using winget. Internet required.',parent=root):
            background(lambda:voices.install_engine(report))
    button(vp,'Install speech engine',engine)
    def voice_download():
        ident=voice_id.get()
        if messagebox.askyesno('Download voice',f'Download {ident}? Review its model card/license before continuing.',parent=root):
            background(lambda:voices.download(ident,report))
    button(vp,'Download selected voice',voice_download)
    def voice_save():
        speaker.close(); voices.model(voice_id.get()); m.config['voice']=voice_id.get(); m.save(); status.set('Voice selected. Enable auto-speak in Settings.')
    button(vp,'Use selected voice',guarded(voice_save))
    def test_voice():
        voice_save(); speaker.start(); speaker.enqueue('നമസ്കാരം. ഞാൻ നിങ്ങളുടെ അസിസ്റ്റന്റ് ആണ്.' if voice_id.get().startswith('ml_') else 'Hello. Your assistant is ready.')
    button(vp,'Test voice',guarded(test_voice))
    def delete_voice():
        if messagebox.askyesno('Delete voice','Delete the selected downloaded voice?',parent=root):
            speaker.close(); voices.delete(voice_id.get()); refresh()
    button(vp,'Delete selected voice',guarded(delete_voice))
    ttk.Label(vp,text='Speech starts after a sentence or short phrase arrives; text continues streaming.\nTTS shares your CPU with inference. Turn it off for maximum generation speed.\nAudio is kept in RAM, not written to WAV files. English voices do not speak Malayalam reliably.',wraplength=830).pack(anchor='w',pady=8)

    sp=pages['Settings']; variables={}
    numeric=[('threads','CPU threads'),('context','Context tokens'),('batch','Prompt batch'),('ubatch','Micro-batch'),
             ('load_timeout','Load timeout (seconds)'),('max_tokens','Maximum reply tokens'),('temperature','Temperature'),
             ('history_turns','Remembered exchanges'),('memory_kb','Saved memory cap (KB)'),('speech_rate','Speech rate (0.5–2)'),('port','Local API port')]
    grid=ttk.Frame(sp); grid.pack(fill='x')
    for i,(key,label) in enumerate(numeric):
        row,col=divmod(i,2); variables[key]=tk.StringVar(value=str(m.config[key]))
        ttk.Label(grid,text=label).grid(row=row,column=col*2,sticky='w',padx=4,pady=5)
        ttk.Entry(grid,textvariable=variables[key],width=13).grid(row=row,column=col*2+1,padx=(4,25))
    ttk.Label(grid,text='Loading mode').grid(row=5,column=2,sticky='w',padx=4)
    variables['load_mode']=tk.StringVar(value=m.config['load_mode'])
    ttk.Combobox(grid,values=['mmap','none'],textvariable=variables['load_mode'],state='readonly',width=11).grid(row=5,column=3)
    checks=ttk.Frame(sp); checks.pack(fill='x',pady=8)
    for i,(key,label) in enumerate([('warmup','Warm up model on load'),('autoload','Load selected model on app startup'),
                                  ('use_memory','Include conversation and facts in prompts'),('persist_memory','Save encrypted memory between sessions'),
                                  ('auto_speak','Speak while generating'),('debug_logs','Diagnostic server logs (may contain sensitive data)')]):
        variables[key]=tk.BooleanVar(value=m.config[key]); ttk.Checkbutton(checks,text=label,variable=variables[key]).grid(row=i,sticky='w',pady=3)
    def settings_save():
        if m.running(): raise ValueError('Unload the model before changing settings.')
        old=m.config.copy(); speaker.close()
        try:
            for key,var in variables.items():
                value=var.get()
                if key in ('temperature','speech_rate'): value=float(value)
                elif isinstance(old[key],int) and not isinstance(old[key],bool): value=int(value)
                m.config[key]=value
            m.save(); memory.save(); refresh(); status.set('Settings saved. Reload a model to apply.')
        except Exception:
            m.config.clear(); m.config.update(old); m.save(); raise
    button(sp,'Save settings',guarded(settings_save))
    def fast():
        for key,value in {'threads':min(4,m.config['threads']),'context':2048,'batch':128,'ubatch':128,'max_tokens':256,'history_turns':6,'auto_speak':False}.items(): variables[key].set(value)
        status.set('Low-memory preset filled. Save settings to apply; hardware speed is not guaranteed.')
    button(sp,'Fill low-memory / shorter-reply preset',fast)
    ttk.Label(sp,text='Larger context and more history consume RAM and increase prompt processing time.\nModel files, voice files and preferences are not encrypted; saved Nila memory is.\nChanging persistence to OFF deletes its saved encrypted copy on Save.',wraplength=830).pack(anchor='w',pady=6)
    def cancel(unload_model=False):
        m.cancel.set(); chat.stop(); speaker.stop()
        if generating[0] or unload_model:
            # Kill the owned local server off the UI thread to unblock streaming reads.
            threading.Thread(target=m.stop,daemon=True).start()
        status.set('Stopping current operation…')
    ttk.Button(frame,text='Cancel current operation',command=cancel).pack(anchor='e',pady=5)
    def close():
        if busy[0]: cancel(); status.set('Stopping… close again when the operation finishes.'); return
        speaker.close(); m.stop(); root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    refresh(); tick()
    if m.config['autoload'] and m.config['model'] and m.config['name']: root.after(250,guarded(load))
    root.mainloop()
