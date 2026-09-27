"""Downloadable Piper voices and nonblocking incremental response speech."""
import base64
import json
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from .core import ROOT, download, Cancelled

VOICES = {
    'en_US-amy-low': ('English · Amy', 'en/en_US/amy/low'),
    'en_US-lessac-medium': ('English · Lessac', 'en/en_US/lessac/medium'),
    'ml_IN-meera-medium': ('Malayalam · Meera', 'ml/ml_IN/meera/medium'),
}
BASE = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/'


class SentenceBuffer:
    """Short ordered chunks; suppress fenced code and raw <think> content."""
    def __init__(self):
        self.pending=''
        self.code=False
        self.think=False

    def feed(self, text):
        self.pending+=text
        out=[]
        while True:
            # Process complete lines/sentences or a bounded phrase at whitespace.
            match=re.search(r'[.!?।]\s|\n',self.pending)
            end=match.end() if match else 0
            if not end and len(self.pending)>240:
                end=self.pending.rfind(' ',0,240)+1
                if not end: end=240
            if not end: break
            chunk,self.pending=self.pending[:end],self.pending[end:]
            cleaned=self.clean(chunk)
            if cleaned: out.append(cleaned)
        return out

    def clean(self, chunk):
        # State persists across chunks, including multiline fences/thoughts.
        result=[]
        for part in re.split(r'(```|<think>|</think>)',chunk):
            if part=='```': self.code=not self.code
            elif part=='<think>': self.think=True
            elif part=='</think>': self.think=False
            elif not self.code and not self.think: result.append(part)
        text=''.join(result)
        text=re.sub(r'https?://\S+','',text)
        text=re.sub(r'[`*_#]','',text).strip()
        return text

    def finish(self):
        text=self.clean(self.pending); self.pending=''
        return [text] if text else []


class Voices:
    def __init__(self,manager):
        self.manager=manager
        self.home=manager.home/'voices'
        self.home.mkdir(parents=True,exist_ok=True)
        self.python=manager.home/'speech-env'/'Scripts'/'python.exe'

    def model(self, voice):
        if voice not in VOICES: raise ValueError('Choose a voice from the voice catalog.')
        p=self.home/voice/(voice+'.onnx')
        if not p.exists() or not p.with_suffix('.onnx.json').exists():
            raise FileNotFoundError('Download the selected voice first.')
        return p

    def installed(self):
        return [name for name in VOICES if (self.home/name/(name+'.onnx')).exists()]

    def install_engine(self, progress=print):
        progress('Installing optional Piper speech engine and Python if needed…')
        args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'voice_setup.ps1'),
              '-Target',str(self.python.parent.parent)]
        if not getattr(sys,'frozen',False): args+=['-PythonPath',sys.executable]
        child=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        start=time.monotonic()
        try:
            while True:
                if self.manager.cancel.is_set(): raise Cancelled('Speech engine installation cancelled; retry to repair.')
                if time.monotonic()-start>900: raise TimeoutError('Speech engine installation timed out.')
                try:
                    _,error=child.communicate(timeout=.3)
                    break
                except subprocess.TimeoutExpired: pass
            if child.returncode:
                raise RuntimeError('Speech engine installation failed. Install Python 3.12 x64 and retry. '+error.decode(errors='replace')[-600:])
            progress('Piper installed. Download a voice next.')
        finally:
            if child.poll() is None:
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                child.wait()

    def download(self, voice, progress=print):
        if voice not in VOICES: raise ValueError('Unknown voice ID.')
        destination=self.home/voice
        if destination.exists():
            self.model(voice)
            progress('Voice already downloaded.')
            return
        with tempfile.TemporaryDirectory(dir=self.home) as temp:
            temp=Path(temp)
            base=BASE+VOICES[voice][1]+'/'
            for filename in (voice+'.onnx',voice+'.onnx.json','MODEL_CARD'):
                download(base+filename,temp/filename,progress,self.manager.cancel)
            cfg=json.loads((temp/(voice+'.onnx.json')).read_text(encoding='utf-8'))
            if 'audio' not in cfg or 'phoneme_id_map' not in cfg: raise ValueError('Invalid voice configuration.')
            if (temp/(voice+'.onnx')).stat().st_size < 1024: raise ValueError('Incomplete voice model.')
            # Atomic directory promotion; failed multi-file downloads leave no installed voice.
            temp.rename(destination)
        progress('Voice downloaded. Review its model card before use.')

    def delete(self,voice):
        if voice not in VOICES: raise ValueError('Unknown voice ID.')
        shutil.rmtree(self.home/voice,ignore_errors=False)


class Speaker:
    def __init__(self,manager,report=lambda s:None):
        self.manager=manager
        self.voices=Voices(manager)
        self.report=report
        self.items=queue.Queue(maxsize=24)
        self.worker=None
        self.process=None
        self.disabled=threading.Event()
        self.ending=threading.Event()
        self.io_lock=threading.Lock()

    def start(self):
        if self.worker and self.worker.is_alive(): return
        if not self.voices.python.exists(): raise FileNotFoundError('Install the speech engine first.')
        self.voices.model(self.manager.config['voice'])
        self.disabled.clear(); self.ending.clear()
        self.worker=threading.Thread(target=self._loop,daemon=True)
        self.worker.start()

    def enqueue(self,text):
        if self.disabled.is_set() or not text.strip(): return
        try: self.items.put_nowait(text)
        except queue.Full:
            self.stop()
            self.report('Speech stopped because it fell behind generation. Text continues; lower speech load or shorten replies.')

    def _launch(self):
        model=self.voices.model(self.manager.config['voice'])
        self.process=subprocess.Popen([str(self.voices.python),'-u',str(ROOT/'speech_worker.py'),str(model),
                                       str(self.manager.config['speech_rate'])],stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',
                                      creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        ready=self.process.stdout.readline()
        if not ready or not json.loads(ready).get('ready'):
            raise RuntimeError('Voice could not load. Reinstall the engine/voice.')

    def _loop(self):
        try:
            import winsound
            self._launch()
            while not self.ending.is_set():
                try: text=self.items.get(timeout=.2)
                except queue.Empty: continue
                try:
                    if self.disabled.is_set(): continue
                    self.process.stdin.write(json.dumps({'text':text},ensure_ascii=False)+'\n')
                    self.process.stdin.flush()
                    line=self.process.stdout.readline()
                    if not line: raise RuntimeError('Speech worker stopped unexpectedly.')
                    result=json.loads(line)
                    if 'error' in result: raise RuntimeError(result['error'])
                    data=base64.b64decode(result['wav'],validate=True)
                    if not self.disabled.is_set():
                        # WAV remains only in memory; synchronous playback preserves sentence order.
                        winsound.PlaySound(data,winsound.SND_MEMORY|winsound.SND_NODEFAULT)
                finally: self.items.task_done()
        except Exception as e:
            if not self.ending.is_set(): self.report(str(e))
            self.disabled.set()
        finally:
            self._kill()
            self._drain()

    def _drain(self):
        while True:
            try: self.items.get_nowait(); self.items.task_done()
            except queue.Empty: break

    def _kill(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=3)
                except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
            for pipe in (self.process.stdin,self.process.stdout):
                if pipe:
                    try: pipe.close()
                    except OSError: pass
            self.process=None

    def stop(self):
        self.disabled.set(); self.ending.set(); self._drain()
        try:
            import winsound
            winsound.PlaySound(None,0)
        except (ImportError,RuntimeError): pass
        # Terminate makes any blocking synthesis read return immediately.
        if self.process and self.process.poll() is None: self.process.terminate()

    def close(self):
        self.stop()
        if self.worker: self.worker.join(timeout=5)
