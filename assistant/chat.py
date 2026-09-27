"""Authenticated local streaming client shared by the desktop and terminal."""
import json
import threading
import time
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
from .core import prompt, Cancelled


class Chat:
    def __init__(self, manager, memory):
        self.manager, self.memory = manager, memory
        self.cancel = threading.Event()
        self.response = None
        # Loopback inference must never be forwarded through an environment proxy.
        self.http = build_opener(ProxyHandler({}))
        self.last_stats = {}

    def request(self, path, body):
        m=self.manager
        return Request(f'http://127.0.0.1:{m.active_port}{path}',
                       data=json.dumps(body,ensure_ascii=False).encode('utf-8'),
                       headers={'Content-Type':'application/json','Authorization':'Bearer '+m.api_key})

    def post(self, path, body):
        with self.http.open(self.request(path,body),timeout=30) as r:
            return json.load(r)

    def fit_context(self, messages):
        c=self.manager.config
        budget = self.manager.active_context - c['max_tokens'] - 32
        while True:
            if self.cancel.is_set(): raise Cancelled('Generation cancelled.')
            rendered=self.post('/apply-template',{'messages':messages})['prompt']
            count=len(self.post('/tokenize',{'content':rendered,'add_special':True,'parse_special':True})['tokens'])
            if count <= budget: return messages, count
            if len(messages)<=2:
                raise ValueError('Your message and saved facts do not fit this context. '
                                 'Shorten them, lower maximum reply tokens, or reload with a larger context.')
            # Remove an entire oldest exchange, never orphan an assistant message.
            del messages[1:3]

    def stop(self):
        self.cancel.set()
        # Closing a socket stream can block during a read on some Python versions.
        # The worker handles cancellation at each SSE event; UI also unloads if needed.

    def stream(self, user, on_text, on_speech=None):
        if not self.manager.running() or not self.manager.api_key:
            raise ValueError('Load a model for Nila Chat first.')
        user=user.strip()
        if not user: raise ValueError('Enter a message.')
        if len(user)>100000: raise ValueError('Message is too long.')
        self.cancel.clear()
        started=time.monotonic()
        messages, input_tokens=self.fit_context(self.memory.messages(prompt(self.manager.config['name']),user))
        body={'model':self.manager.config['name'],'messages':messages,'stream':True,
              'max_tokens':self.manager.config['max_tokens'],'temperature':self.manager.config['temperature'],
              'cache_prompt':True}
        parts=[]; first=None; complete=False
        from .speech import SentenceBuffer
        sentences=SentenceBuffer()
        try:
            self.response=self.http.open(self.request('/v1/chat/completions',body),timeout=60)
            with self.response as response:
                for raw in response:
                    if self.cancel.is_set(): raise Cancelled('Generation cancelled; partial answer was not saved.')
                    if not raw.startswith(b'data:'): continue
                    data=raw[5:].strip()
                    if data==b'[DONE]':
                        complete=True
                        break
                    if not data: continue
                    event=json.loads(data)
                    if 'error' in event: raise RuntimeError('Model rejected this request. Try a shorter message.')
                    choices=event.get('choices',[])
                    if not choices: continue
                    chunk=choices[0].get('delta',{}).get('content') or ''
                    # Never speak reasoning_content / internal thought fields.
                    if chunk:
                        if first is None: first=time.monotonic()-started
                        parts.append(chunk); on_text(chunk)
                        if on_speech:
                            for sentence in sentences.feed(chunk): on_speech(sentence)
            if self.cancel.is_set(): raise Cancelled('Generation cancelled; partial answer was not saved.')
            if not complete: raise ConnectionError('Generation stream ended early; partial answer was not saved.')
            if on_speech:
                for sentence in sentences.finish(): on_speech(sentence)
            answer=''.join(parts)
            if answer: self.memory.append(user,answer)
            self.last_stats={'first_token_seconds':first,'elapsed_seconds':time.monotonic()-started,
                             'input_tokens':input_tokens,'retained_turns':(len(messages)-2)//2}
            return answer
        except HTTPError as e:
            raise RuntimeError(f'Local model request failed (HTTP {e.code}). Check context size/model compatibility.') from None
        finally:
            self.response=None
