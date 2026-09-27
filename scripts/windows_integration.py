"""Real Windows smoke tests, including tiny-model inference and Piper synthesis.
Only synthetic test text is used. No private data is uploaded.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from assistant.core import Manager, CATALOG, ROOT
from assistant.memory import Memory
from assistant.chat import Chat
from assistant.speech import Voices


def main():
    with tempfile.TemporaryDirectory() as tmp:
        m=Manager(Path(tmp)); m.config.update(name='Nila',max_tokens=32,context=1024,debug_logs=True,persist_memory=True)
        m.save(); m.install_runtime()
        m.config['model']=m.download_model(CATALOG[0][1]); m.save()
        mem=Memory(m.home,m.config); mem.remember('The test color is turquoise.')
        assert b'turquoise' not in mem.path.read_bytes()
        assert Memory(m.home,m.config).facts==mem.facts
        try:
            url=m.start_ui()
            try:
                urlopen(Request(url+'/v1/chat/completions',data=b'{"messages":[]}',headers={'Content-Type':'application/json'}),timeout=10)
                raise AssertionError('Unauthenticated completion unexpectedly succeeded')
            except HTTPError as e: assert e.code==401,e.code
            chunks=[]
            reply=Chat(m,mem).stream('Say hello in one short sentence.',chunks.append)
            assert reply.strip() and chunks
            assert Memory(m.home,m.config).turns
            print('PASS: protected server, real streamed model response, encrypted conversation',flush=True)
        except Exception:
            log=m.home/'server.log'
            if log.exists(): print(log.read_text(errors='replace')[-12000:])
            raise
        finally: m.stop()
        v=Voices(m); v.install_engine()
        for voice,text in [('en_US-amy-low','Hello. This is a test.'),('ml_IN-meera-medium','നമസ്കാരം.')]:
            v.download(voice)
            response=subprocess.run([str(v.python),'-u',str(ROOT/'speech_worker.py'),str(v.model(voice)),'1.0'],
                                    input=json.dumps({'text':text})+'\n',capture_output=True,text=True,encoding='utf-8',timeout=120)
            assert response.returncode==0,response.stderr
            lines=[json.loads(line) for line in response.stdout.splitlines() if line.strip()]
            assert lines[0]['ready']
            wav=base64.b64decode(lines[1]['wav'])
            assert wav[:4]==b'RIFF' and len(wav)>1000
            print('PASS: downloaded '+voice+' and synthesized WAV in memory',flush=True)
    print('Integration passed; physical speaker playback and manual UX still require a user test.')

if __name__=='__main__': main()
