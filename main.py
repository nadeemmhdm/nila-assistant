import argparse
import platform
import sys
import webbrowser
from assistant.core import Manager, instance_lock


def main():
    p=argparse.ArgumentParser(description='Local Assistant — Windows local AI chat, powered by llama.cpp')
    p.add_argument('command',nargs='?',default='gui',choices=['gui','setup','models','download','import','delete','chat','web','runtime'])
    p.add_argument('value',nargs='?')
    args=p.parse_args()
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64','x86_64'):
        p.error('This release supports Windows x64 only.')
    with instance_lock():
        return execute(args, p)


def execute(args, p):
    if args.command=='gui':
        from assistant.gui import run
        run()
        return
    m=Manager()
    try:
        if args.command=='setup':
            m.config['name']=input('What would you like to name your AI assistant? ').strip()
            m.save()
            m.install_runtime()
            print('Setup complete. Download/import a model next, or open the GUI.')
        elif args.command=='runtime': m.install_runtime()
        elif args.command=='models': print('\n'.join(m.installed()) or 'No models installed.')
        elif args.command in ('download','import','delete'):
            if not args.value: p.error('This command requires a URL or filename.')
            if args.command=='delete':
                if input('Delete managed model? Type DELETE: ')=='DELETE': m.delete_model(args.value)
            else:
                m.config['model']=(m.download_model(args.value) if args.command=='download' else m.import_model(args.value))
                m.save()
        elif args.command in ('chat','web'):
            if args.value: m.config['model']=args.value
            if args.command=='chat':
                import subprocess
                m.process=subprocess.Popen(m.cli_args())
                m.process.wait()
            else:
                url=m.start_ui()
                webbrowser.open(url)
                input('Web chat is running. Press Enter to unload the model and exit.\n')
    except (Exception,KeyboardInterrupt) as e:
        print(f'Error: {e}',file=sys.stderr)
        return 1
    finally: m.stop()
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        input('Press Enter to close. ')
        raise SystemExit(1)
