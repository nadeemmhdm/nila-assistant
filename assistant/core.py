"""Local model management. No cloud inference and no third-party Python dependencies."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, unquote
import zipfile
from contextlib import contextmanager

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
DATA = Path(os.environ.get('LOCAL_ASSISTANT_HOME', str(Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'LocalAssistant')))
CATALOG = [
    ('Qwen 2.5 0.5B Instruct · small starter', 'https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf', 'https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF'),
    ('Qwen 2.5 1.5B Instruct · larger', 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf', 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF'),
]

class Cancelled(Exception):
    pass


@contextmanager
def instance_lock(home=DATA):
    """OS-held lock is released even if the launcher crashes."""
    import msvcrt
    Path(home).mkdir(parents=True, exist_ok=True)
    with (Path(home) / 'launcher.lock').open('a+b') as handle:
        handle.write(b'0')
        handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as e:
            raise RuntimeError('Local Assistant is already open. Close the other manager first.') from e
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def validate_name(name):
    name = name.strip()
    if not name or len(name) > 60 or any(ord(c) < 32 for c in name):
        raise ValueError('Use an assistant name of 1–60 characters, without line breaks.')
    return name


def prompt(name):
    return ('You are a personal AI chat assistant. Your chosen name is ' +
            json.dumps(validate_name(name), ensure_ascii=False) +
            '. Use this name when asked who you are. Respond in the language the user uses. '
            'Be helpful, honest and concise. You cannot browse the web or operate the computer.')


def safe_filename(name):
    if not name or len(name) > 180 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.endswith((' ', '.')):
        raise ValueError('Invalid model filename.')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        raise ValueError('Reserved Windows filename.')
    if not name.lower().endswith('.gguf') or re.search(r'-\d{5}-of-\d{5}', name):
        raise ValueError('Choose a single-file .gguf model. Split GGUF files are not supported in v0.1.')
    return name


def validate_gguf(path):
    with Path(path).open('rb') as f:
        if f.read(4) != b'GGUF' or Path(path).stat().st_size < 24:
            raise ValueError('This is not a valid GGUF file (possibly an HTML download error).')


def https_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise ValueError('A public HTTPS download URL is required.')
    return url


def download(url, target, progress=lambda s: None, cancel=None, sha256=None, gguf=False):
    """Atomic replacement; incomplete downloads are never exposed as models."""
    https_url(url)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + '.part')
    digest = hashlib.sha256()
    try:
        request = Request(url, headers={'User-Agent':'LocalAssistant/0.1', 'Accept-Encoding':'identity'})
        with urlopen(request, timeout=30) as response:
            https_url(response.geturl())
            total = int(response.headers.get('Content-Length', 0))
            if total and shutil.disk_usage(target.parent).free < total + 64 * 1024**2:
                raise OSError('Not enough disk space for this download.')
            done = 0
            last = 0.0
            with part.open('wb') as out:
                while True:
                    if cancel and cancel.is_set():
                        raise Cancelled('Download cancelled.')
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    out.write(block)
                    digest.update(block)
                    done += len(block)
                    if time.monotonic() - last > .25:
                        progress(f'Downloaded {done/1024**2:.1f} MiB' + (f' / {total/1024**2:.1f} MiB' if total else ''))
                        last = time.monotonic()
            if total and total != done:
                raise OSError('Incomplete download. Retry when your connection is stable.')
        if sha256 and digest.hexdigest().lower() != sha256.lower():
            raise ValueError('SHA-256 mismatch. The downloaded file was not installed.')
        if gguf:
            validate_gguf(part)
        os.replace(part, target)
        progress('Download complete.')
        return digest.hexdigest()
    finally:
        part.unlink(missing_ok=True)


def safe_extract(archive, dest):
    dest = Path(dest).resolve()
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            name = item.filename.replace('\\', '/')
            if ':' in name or not (dest / name).resolve().is_relative_to(dest):
                raise ValueError('Unsafe path in runtime archive.')
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Links are not accepted in runtime archives.')
        z.extractall(dest)


class Manager:
    def __init__(self, home=DATA):
        self.home = Path(home)
        self.models = self.home / 'models'
        self.models.mkdir(parents=True, exist_ok=True)
        self.config_path = self.home / 'config.json'
        self.config = {'name':'', 'model':'', 'threads':min(4, os.cpu_count() or 2), 'context':2048, 'port':8080,
                       'batch':128, 'ubatch':128, 'load_mode':'mmap', 'warmup':True,
                       'load_timeout':300, 'autoload':False, 'max_tokens':512, 'temperature':0.7,
                       'use_memory':True, 'persist_memory':False, 'history_turns':12, 'memory_kb':256,
                       'auto_speak':False, 'voice':'en_US-amy-low', 'speech_rate':1.0, 'debug_logs':False}
        if self.config_path.exists():
            self.config.update(json.loads(self.config_path.read_text(encoding='utf-8')))
        self.process = None
        self.process_lock = threading.RLock()
        self.api_key = ''
        self.active_port = self.config['port']
        self.active_context = self.config['context']
        self.log = None
        self.cancel = threading.Event()

    def save(self):
        validate_name(self.config['name'])
        for key, lo, hi in [('threads',1,256),('context',512,32768),('port',1024,65535),('batch',32,2048),('ubatch',32,512),('load_timeout',30,900),('max_tokens',32,4096),('history_turns',0,200),('memory_kb',32,2048)]:
            if not lo <= int(self.config[key]) <= hi:
                raise ValueError(f'{key} must be between {lo} and {hi}.')
            self.config[key] = int(self.config[key])
        if self.config['ubatch'] > self.config['batch']:
            raise ValueError('Micro-batch must not exceed batch size.')
        if self.config['max_tokens'] >= self.config['context'] - 128:
            raise ValueError('Maximum reply tokens must leave at least 128 context tokens for input.')
        if self.config['load_mode'] not in ('mmap','none'):
            raise ValueError('Load mode must be mmap or none.')
        for key,lo,hi in [('temperature',0,2),('speech_rate',0.5,2.0)]:
            self.config[key] = float(self.config[key])
            if not lo <= self.config[key] <= hi: raise ValueError(f'{key} must be {lo}–{hi}.')
        for key in ('warmup','autoload','use_memory','persist_memory','auto_speak','debug_logs'):
            if not isinstance(self.config[key],bool): raise ValueError(f'{key} must be true or false.')
        atomic_json(self.config_path, self.config)

    def installed(self):
        return sorted(p.name for p in self.models.glob('*.gguf') if p.is_file())

    def selected(self):
        p = self.models / safe_filename(self.config['model'])
        validate_gguf(p)
        return p

    def import_model(self, source):
        source = Path(source).resolve()
        name = safe_filename(source.name)
        validate_gguf(source)
        target = self.models / name
        if source == target.resolve():
            return name
        if target.exists():
            raise ValueError('A model with this filename already exists.')
        part = target.with_suffix('.gguf.part')
        try:
            shutil.copyfile(source, part)
            validate_gguf(part)
            part.replace(target)
        finally:
            part.unlink(missing_ok=True)
        return name

    def download_model(self, url, progress=print):
        https_url(url)
        name = safe_filename(Path(unquote(urlsplit(url).path)).name)
        target = self.models / name
        if target.exists():
            raise ValueError('This model already exists. Remove it before downloading again.')
        digest = download(url, target, progress, self.cancel, gguf=True)
        atomic_json(target.with_suffix('.json'), {'url':url,'sha256':digest})
        return name

    def delete_model(self, name):
        if self.running():
            raise ValueError('Unload the active model before deleting models.')
        target = self.models / safe_filename(name)
        target.unlink()
        target.with_suffix('.json').unlink(missing_ok=True)
        if self.config['model'] == name:
            self.config['model'] = ''
            self.save()

    def runtime_dir(self):
        manifest = json.loads((ROOT / 'runtime.json').read_text())
        return self.home / 'runtime' / manifest['tag']

    def executable(self, name):
        matches = list(self.runtime_dir().rglob(name + '.exe'))
        if not matches:
            raise FileNotFoundError('Install llama.cpp runtime first.')
        return matches[0]

    def install_runtime(self, progress=print):
        if self.running():
            raise ValueError('Unload the model before installing the runtime.')
        if self.runtime_dir().exists():
            self.executable('llama-server')
            self.executable('llama-cli')
            progress('Runtime already installed.')
            return
        manifest = json.loads((ROOT / 'runtime.json').read_text())
        with tempfile.TemporaryDirectory(dir=self.home) as temp:
            temp = Path(temp)
            archive = temp / 'runtime.zip'
            progress('Downloading official Windows x64 CPU runtime…')
            download(manifest['url'], archive, progress, self.cancel, manifest['sha256'])
            unpacked = temp / 'unpacked'
            safe_extract(archive, unpacked)
            if not list(unpacked.rglob('llama-server.exe')) or not list(unpacked.rglob('llama-cli.exe')):
                raise ValueError('The runtime archive is missing required executables.')
            self.runtime_dir().parent.mkdir(parents=True, exist_ok=True)
            unpacked.rename(self.runtime_dir())
        progress('Runtime installed and SHA-256 verified.')

    def base_args(self, exe):
        self.save()
        return [str(self.executable(exe)), '-m',str(self.selected()), '-t',str(self.config['threads']),
                '-c',str(self.config['context']), '-b',str(self.config['batch']),
                '-ub',str(self.config['ubatch']),'-ngl','0','--load-mode',self.config['load_mode'],
                '--warmup' if self.config['warmup'] else '--no-warmup']

    def server_args(self):
        args = self.base_args('llama-server')
        ui_file = self.home / 'webui.json'
        atomic_json(ui_file, {'systemMessage':prompt(self.config['name']), 'showSystemMessage':True,
                             'titleGenerationUseLLM':False,'jsSandboxEnabled':False,'mcpServers':[],
                             'temperature':self.config['temperature'],'max_tokens':self.config['max_tokens']})
        return args + ['--host','127.0.0.1','--port',str(self.config['port']),'-np','1',
                       '--alias',self.config['name'],'--ui-config-file',str(ui_file),'--cors-origins','localhost']

    def cli_args(self):
        return self.base_args('llama-cli') + ['-sys',prompt(self.config['name'])]

    def running(self):
        process = self.process
        return process is not None and process.poll() is None

    def start_ui(self, progress=print):
        if self.running():
            raise ValueError('Unload the current model first.')
        args = self.server_args()
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', self.config['port']))
            except OSError as e:
                raise ValueError('Port is already in use. Change the port in Settings.') from e
        self.api_key = secrets.token_urlsafe(32)
        self.active_port = self.config['port']
        self.active_context = self.config['context']
        child_env = {k:v for k,v in os.environ.items() if not k.startswith('LLAMA_')}
        child_env['LLAMA_API_KEY'] = self.api_key
        self.log = ((self.home / 'server.log').open('w',encoding='utf-8')
                    if self.config['debug_logs'] else open(os.devnull,'w'))
        try:
            self.process = subprocess.Popen(args, stdout=self.log, stderr=subprocess.STDOUT, env=child_env,
                                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except BaseException:
            self.log.close()
            self.log = None
            raise
        url = f"http://127.0.0.1:{self.config['port']}"
        progress('Loading model into memory…')
        try:
            for _ in range(self.config['load_timeout'] * 2):
                if self.cancel.is_set():
                    raise Cancelled('Model loading cancelled.')
                if not self.running():
                    raise RuntimeError('llama-server stopped. Check your model/runtime; enable diagnostic logs in Settings for details.')
                try:
                    with urlopen(url + '/health',timeout=.5) as res:
                        if res.status == 200:
                            progress('Model ready. Protected local chat is running.')
                            return url
                except OSError:
                    pass
                time.sleep(.5)
            raise TimeoutError('Model load timed out. Try a smaller model or increase the load timeout.')
        except BaseException:
            self.stop()
            raise

    def start_cli(self):
        if self.running():
            raise ValueError('Unload the current model first.')
        self.process = subprocess.Popen(self.cli_args(), creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))

    def stop(self):
        with self.process_lock:
            if self.running():
                if sys.platform == 'win32':
                    subprocess.run(['taskkill','/PID',str(self.process.pid),'/T','/F'],
                                   capture_output=True, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                else:
                    self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process = None
            self.api_key = ''
            if self.log:
                self.log.close()
                self.log = None
