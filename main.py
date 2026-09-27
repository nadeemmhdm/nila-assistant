import argparse
import json
import platform
import subprocess
import sys
import webbrowser
from assistant.core import Manager, instance_lock, CATALOG
from assistant.memory import Memory
from assistant.chat import Chat
from assistant.speech import Voices, Speaker, VOICES


def parser():
    p=argparse.ArgumentParser(description='Nila Assistant — private local chat, memory and offline speech for Windows')
    commands=p.add_subparsers(dest='command')
    commands.add_parser('gui')
    setup=commands.add_parser('setup',help='Name assistant, install runtime and optionally download a model/voice')
    setup.add_argument('--name'); setup.add_argument('--model',help='small, balanced, or direct GGUF URL')
    setup.add_argument('--speech',action='store_true'); setup.add_argument('--voice',choices=list(VOICES),default='en_US-amy-low')
    commands.add_parser('models'); commands.add_parser('runtime')
    for cmd in ('download','import','delete'):
        commands.add_parser(cmd).add_argument('value')
    for cmd in ('chat','web','load','native-chat'):
        command=commands.add_parser(cmd)
        command.add_argument('--model',help='Installed GGUF filename')
        if cmd=='chat': command.add_argument('--speak',action='store_true')
    voice=commands.add_parser('voice'); voice.add_argument('action',choices=['list','install','download','use','delete','test'])
    voice.add_argument('id',nargs='?',choices=list(VOICES))
    memory=commands.add_parser('memory'); memory.add_argument('action',choices=['list','add','forget','clear','clear-history']); memory.add_argument('value',nargs='?')
    settings=commands.add_parser('settings'); settings.add_argument('action',choices=['list','set']); settings.add_argument('key',nargs='?'); settings.add_argument('value',nargs='?')
    return p


def model_url(value):
    return {'small':CATALOG[0][1],'balanced':CATALOG[1][1]}.get(value,value)


def cli_chat(m,speak=False):
    memory=Memory(m.home,m.config); chat=Chat(m,memory)
    speaker=Speaker(m,lambda msg:print('\n[Speech] '+msg))
    try:
        m.start_ui()
        if speak or m.config['auto_speak']: speaker.start()
        print('Commands: /quit /new /remember FACT /memory /forget NUMBER /clear /unload /load FILENAME /stop-speech')
        while True:
            text=input('\nYou: ').strip()
            if not text: continue
            if text=='/quit': break
            if text=='/new': memory.clear(facts=False); print('Conversation cleared.'); continue
            if text=='/memory':
                for i,fact in enumerate(memory.facts,1): print(f'{i}. {fact}')
                continue
            if text.startswith('/remember '): memory.remember(text[10:]); print('Remembered.'); continue
            if text.startswith('/forget '): memory.forget(int(text[8:])-1); print('Forgotten.'); continue
            if text=='/clear':
                if input('Clear all memory? Type CLEAR: ')=='CLEAR': memory.clear()
                continue
            if text=='/stop-speech': speaker.stop(); continue
            if text=='/unload': speaker.close(); m.stop(); print('Model unloaded.'); continue
            if text.startswith('/load '):
                speaker.close(); m.stop(); m.config['model']=text[6:].strip(); m.save(); m.start_ui(); continue
            if text.startswith('/'): print('Unknown command.'); continue
            print(m.config['name']+': ',end='',flush=True)
            try:
                if speak or m.config['auto_speak']: speaker.start()
                chat.stream(text,lambda chunk:print(chunk,end='',flush=True),speaker.enqueue if speak or m.config['auto_speak'] else None)
                print()
            except KeyboardInterrupt:
                chat.stop(); speaker.stop(); m.stop(); print('\nCancelled. Use /load FILENAME to reload.')
            except Exception as e:
                speaker.stop(); print('\n'+str(e))
    finally: speaker.close(); m.stop()


def execute(args):
    if args.command in (None,'gui'):
        from assistant.gui import run
        run(); return 0
    m=Manager(); voices=Voices(m)
    try:
        if args.command=='setup':
            m.config['name']=args.name or input('What would you like to name your AI assistant? ').strip()
            m.save(); m.install_runtime()
            if args.model:
                url=model_url(args.model)
                from pathlib import Path
                from urllib.parse import urlsplit, unquote
                name=Path(unquote(urlsplit(url).path)).name
                m.config['model']=name if name in m.installed() else m.download_model(url)
                m.save()
            if args.speech:
                voices.install_engine(); voices.download(args.voice); m.config['voice']=args.voice; m.config['auto_speak']=True; m.save()
            print('Setup complete. Run chat or gui. Memory persistence is off unless explicitly enabled.')
        elif args.command=='runtime': m.install_runtime()
        elif args.command=='models': print('\n'.join(m.installed()) or 'No models installed.')
        elif args.command in ('download','import','delete'):
            if not m.config['name']: raise ValueError('Run setup --name YOUR_NAME first.')
            if args.command=='delete':
                if input('Delete managed model? Type DELETE: ')=='DELETE': m.delete_model(args.value)
            else:
                m.config['model']=(m.download_model(model_url(args.value)) if args.command=='download' else m.import_model(args.value)); m.save()
        elif args.command=='settings':
            if args.action=='list': print(json.dumps(m.config,ensure_ascii=False,indent=2))
            else:
                if args.key not in m.config or args.value is None: raise ValueError('Provide a known setting key and value. Run settings list.')
                memory=Memory(m.home,m.config)
                old=m.config[args.key]
                if isinstance(old,bool):
                    if args.value.lower() not in ('true','false'): raise ValueError('Use true or false.')
                    value=args.value.lower()=='true'
                elif isinstance(old,int): value=int(args.value)
                elif isinstance(old,float): value=float(args.value)
                else: value=args.value
                m.config[args.key]=value
                m.save(); memory.save(); print('Setting saved.')
        elif args.command=='memory':
            if args.action=='clear':
                if input('Clear all saved Nila memory? Type CLEAR: ')=='CLEAR':
                    (m.home/'memory.dpapi').unlink(missing_ok=True); print('Saved memory cleared.')
            else:
                memory=Memory(m.home,m.config)
                if args.action=='list':
                    print(f'{len(memory.turns)} stored exchanges. Persistence: {m.config["persist_memory"]}')
                    for i,fact in enumerate(memory.facts,1): print(f'{i}. {fact}')
                elif args.action=='clear-history': memory.clear(facts=False)
                else:
                    if not m.config['persist_memory']: raise ValueError('Enable persist_memory first for memory across CLI commands, or use /remember inside chat.')
                    if args.value is None: raise ValueError('Provide fact text or a fact number.')
                    if args.action=='add': memory.remember(args.value)
                    else: memory.forget(int(args.value)-1)
        elif args.command=='voice':
            if args.action=='list':
                for id,(label,_) in VOICES.items(): print(id+' — '+label+(' [downloaded]' if id in voices.installed() else ''))
            elif args.action=='install': voices.install_engine()
            elif args.action=='download':
                if not args.id: raise ValueError('Provide a voice ID. Run voice list.')
                voices.download(args.id)
            elif args.action=='delete':
                if not args.id: raise ValueError('Provide a voice ID.')
                if input('Delete voice? Type DELETE: ')=='DELETE': voices.delete(args.id)
            else:
                if args.id: voices.model(args.id); m.config['voice']=args.id; m.save()
                if args.action=='test':
                    speaker=Speaker(m,print)
                    try:
                        speaker.start(); speaker.enqueue('നമസ്കാരം.' if m.config['voice'].startswith('ml_') else 'Hello. Your voice is ready.')
                        input('Press Enter to stop and exit. ')
                    finally: speaker.close()
        elif args.command in ('chat','web','load','native-chat'):
            if args.model: m.config['model']=args.model
            if args.command=='chat': cli_chat(m,args.speak)
            elif args.command=='native-chat':
                m.process=subprocess.Popen(m.cli_args()); m.process.wait()
            else:
                url=m.start_ui()
                if args.command=='web':
                    print('Paste this session key into native Web UI settings (keep it private): '+m.api_key)
                    webbrowser.open(url)
                print('Local API: '+url)
                input('Model is loaded. Press Enter to unload and exit.\n')
        return 0
    finally: m.stop()


def main():
    p=parser(); args=p.parse_args()
    if sys.platform!='win32' or platform.machine().lower() not in ('amd64','x86_64'):
        p.error('This release supports Windows x64 only.')
    try:
        with instance_lock(): return execute(args)
    except (Exception,KeyboardInterrupt) as e:
        print('Error: '+str(e),file=sys.stderr); return 1

if __name__=='__main__': raise SystemExit(main())
