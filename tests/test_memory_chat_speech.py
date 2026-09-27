import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from assistant.core import Manager, Cancelled
from assistant.memory import Memory, DPAPI
from assistant.chat import Chat
from assistant.speech import SentenceBuffer, Voices, Speaker


class FakeProtection:
    # Tests only, never used by production storage.
    def encrypt(self,data): return b'ENC'+base64.b64encode(data)
    def decrypt(self,data):
        if not data.startswith(b'ENC'): raise ValueError('Corrupt data')
        return base64.b64decode(data[3:])


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.m=Manager(Path(self.temp.name))
        self.m.config['name']='Nila'; self.memory=Memory(self.m.home,self.m.config,FakeProtection())
    def tearDown(self): self.temp.cleanup()
    def test_session_only_writes_nothing(self):
        self.memory.remember('Prefer Malayalam.'); self.memory.append('hi','hello')
        self.assertFalse(self.memory.path.exists())
    def test_persistence_roundtrip(self):
        self.m.config['persist_memory']=True
        self.memory.remember('Secret fact'); self.memory.append('hello','hi')
        self.assertNotIn(b'Secret fact',self.memory.path.read_bytes())
        restored=Memory(self.m.home,self.m.config,FakeProtection())
        self.assertEqual(restored.facts,['Secret fact']); self.assertEqual(restored.turns,[['hello','hi']])
    def test_disable_persistence_removes_copy(self):
        self.m.config['persist_memory']=True; self.memory.remember('fact')
        self.m.config['persist_memory']=False; self.memory.save()
        self.assertFalse(self.memory.path.exists())
    def test_turn_capacity_preserves_pairs(self):
        self.m.config['history_turns']=2
        for i in range(5): self.memory.append(str(i),str(i))
        self.assertEqual(self.memory.turns,[['3','3'],['4','4']])
    def test_storage_limit_trims(self):
        self.m.config['memory_kb']=32; self.memory.append('x'*40000,'y'*40000)
        self.assertEqual(self.memory.turns,[])
    def test_zero_turn_capacity(self):
        self.m.config['history_turns']=0; self.memory.append('hello','hi')
        self.assertEqual(self.memory.turns,[])
    def test_fact_removal_and_clear(self):
        self.memory.remember('one'); self.memory.remember('two'); self.memory.forget(0)
        self.assertEqual(self.memory.facts,['two']); self.memory.clear(); self.assertFalse(self.memory.facts)
    def test_facts_separate_from_new_chat(self):
        self.memory.remember('fact'); self.memory.append('a','b'); self.memory.clear(facts=False)
        self.assertEqual(self.memory.facts,['fact']); self.assertFalse(self.memory.turns)
    def test_memory_not_injected_when_disabled(self):
        self.memory.remember('secret'); self.memory.append('a','b'); self.m.config['use_memory']=False
        msgs=self.memory.messages('identity','hi')
        self.assertEqual(len(msgs),2); self.assertNotIn('secret',str(msgs))
    def test_fact_length(self):
        with self.assertRaises(ValueError): self.memory.remember('a'*501)
    def test_corrupt_data_fails_closed(self):
        self.m.config['persist_memory']=True; self.memory.path.write_bytes(b'bad')
        with self.assertRaises(ValueError): Memory(self.m.home,self.m.config,FakeProtection())
    def test_protection_failure_no_plaintext_fallback(self):
        self.m.config['persist_memory']=True; self.memory.protector.encrypt=Mock(side_effect=OSError('denied'))
        with self.assertRaises(OSError): self.memory.remember('secret')
        self.assertFalse(self.memory.path.exists()); self.assertFalse(self.memory.facts)
    @unittest.skipUnless(sys.platform=='win32','Windows DPAPI integration')
    def test_real_windows_dpapi_roundtrip(self):
        secret='നില private memory'.encode(); cipher=DPAPI().encrypt(secret)
        self.assertNotIn(secret,cipher); self.assertEqual(DPAPI().decrypt(cipher),secret)
        with self.assertRaises(OSError): DPAPI().decrypt(b'not dpapi')


class Stream(io.BytesIO):
    pass


def stream_data(chunks,done=True):
    data=b''
    for chunk in chunks:
        data+=('data: '+json.dumps({'choices':[{'delta':chunk}]})+'\n\n').encode()
    if done: data+=b'data: [DONE]\n\n'
    return Stream(data)


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.m=Manager(Path(self.tmp.name)); self.m.config['name']='Nila'
        self.m.process=Mock(); self.m.process.poll.return_value=None; self.m.api_key='secret'
        self.memory=Memory(self.m.home,self.m.config,FakeProtection()); self.chat=Chat(self.m,self.memory)
        self.chat.post=Mock(side_effect=lambda path,body: {'prompt':'rendered'} if path=='/apply-template' else {'tokens':[1,2]})
    def tearDown(self): self.tmp.cleanup()
    def test_stream_order_and_memory_commit(self):
        self.chat.http=Mock(); self.chat.http.open.return_value=stream_data([{'content':'Hello. '},{'content':'Friend!'}])
        chunks=[]; spoken=[]; answer=self.chat.stream('hi',chunks.append,spoken.append)
        self.assertEqual(chunks,['Hello. ','Friend!']); self.assertEqual(spoken,['Hello.','Friend!'])
        self.assertEqual(self.memory.turns,[['hi',answer]])
    def test_reasoning_not_spoken(self):
        self.chat.http=Mock(); self.chat.http.open.return_value=stream_data([{'reasoning_content':'private thought'},{'content':'Answer.'}])
        spoken=[]; self.chat.stream('hi',lambda x:None,spoken.append)
        self.assertEqual(spoken,['Answer.'])
    def test_truncated_stream_not_saved(self):
        self.chat.http=Mock(); self.chat.http.open.return_value=stream_data([{'content':'Partial'}],False)
        with self.assertRaises(ConnectionError): self.chat.stream('hi',lambda x:None)
        self.assertFalse(self.memory.turns)
    def test_cancelled_response_not_saved(self):
        self.chat.http=Mock(); self.chat.http.open.return_value=stream_data([{'content':'Partial'},{'content':'Next'}])
        with self.assertRaises(Cancelled): self.chat.stream('hi',lambda x:self.chat.stop())
        self.assertFalse(self.memory.turns)
    def test_authorization_is_header_not_url(self):
        req=self.chat.request('/tokenize',{'content':'x'})
        self.assertEqual(req.get_header('Authorization'),'Bearer secret'); self.assertNotIn('secret',req.full_url)
    def test_context_trims_complete_old_exchange(self):
        self.memory.turns=[['old','answer'],['recent','reply']]
        calls=[0]
        def post(path,body):
            if path=='/apply-template': return {'prompt':str(len(body['messages']))}
            calls[0]+=1
            return {'tokens':[1]*(9999 if calls[0]==1 else 3)}
        self.chat.post=post
        fitted,_=self.chat.fit_context(self.memory.messages('identity','new'))
        self.assertEqual([x['content'] for x in fitted],['identity','recent','reply','new'])
    def test_oversized_new_prompt_rejected(self):
        self.chat.post=lambda path,body:{'prompt':'long'} if path=='/apply-template' else {'tokens':[1]*9999}
        with self.assertRaises(ValueError): self.chat.fit_context(self.memory.messages('identity','long'))
    def test_no_loaded_model_rejected(self):
        self.m.process=None
        with self.assertRaises(ValueError): self.chat.stream('hi',lambda x:None)


class SpeechTests(unittest.TestCase):
    def test_sentence_stream_and_tail(self):
        b=SentenceBuffer(); self.assertEqual(b.feed('Hello'),[])
        self.assertEqual(b.feed('. Next sentence! '),['Hello.','Next sentence!'])
        b.feed('Tail'); self.assertEqual(b.finish(),['Tail'])
    def test_code_and_thought_suppressed(self):
        b=SentenceBuffer(); out=[]
        for token in ['<thi','nk>private. ','thought</think> Hello. ','```\n','danger()\n','```\n','Done. ']: out+=b.feed(token)
        self.assertEqual(out,['Hello.','Done.'])
    def test_long_sentence_bounded(self):
        b=SentenceBuffer(); out=b.feed('word '*200)
        self.assertTrue(out); self.assertTrue(all(len(x)<=240 for x in out))
    def test_voice_unknown_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            voice=Voices(Manager(Path(tmp)))
            with self.assertRaises(ValueError): voice.model('../../escape')
    def test_queue_saturation_does_not_block_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            speaker=Speaker(Manager(Path(tmp)))
            speaker.stop=Mock()
            for _ in range(25): speaker.enqueue('test')
            speaker.stop.assert_called_once()


class ConfigTests(unittest.TestCase):
    def test_invalid_setting_combinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            for change in [{'ubatch':512,'batch':128},{'context':512,'max_tokens':512},{'speech_rate':0},{'load_mode':'bad'},{'persist_memory':'yes'}]:
                m=Manager(Path(tmp)); m.config['name']='Nila'; m.config.update(change)
                with self.assertRaises(ValueError): m.save()

if __name__=='__main__': unittest.main()
