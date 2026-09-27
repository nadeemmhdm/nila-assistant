import io, json, tempfile, threading, unittest, zipfile
from pathlib import Path
from unittest.mock import patch, Mock
from assistant.core import Manager, prompt, validate_name, safe_filename, download, safe_extract, Cancelled
GGUF=b'GGUF'+b'\0'*100
class Response(io.BytesIO):
    def __init__(self, content, total=None):
        super().__init__(content)
        self.headers={'Content-Length':str(len(content) if total is None else total)}
    def geturl(self): return 'https://huggingface.co/model.gguf'
class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.m=Manager(self.root/'data'); self.m.config['name']='നില'
    def tearDown(self): self.temp.cleanup()
    def model(self):
        source=self.root/'model with spaces.gguf'; source.write_bytes(GGUF)
        self.m.config['model']=self.m.import_model(source)
        return source
    def runtime(self):
        self.m.runtime_dir().mkdir(parents=True)
        for x in ['llama-server.exe','llama-cli.exe']: (self.m.runtime_dir()/x).touch()
    def test_unicode_name_persists(self):
        self.m.save(); self.assertEqual(Manager(self.m.home).config['name'],'നില')
        self.assertIn('നില',prompt('നില'))
    def test_invalid_names(self):
        for n in ['', 'a\nb','a'*61]:
            with self.assertRaises(ValueError): validate_name(n)
    def test_unsafe_filenames_rejected(self):
        for n in ['../bad.gguf','C:\\bad.gguf','CON.gguf','bad.gguf.','x-00001-of-00002.gguf']:
            with self.assertRaises(ValueError): safe_filename(n)
    def test_import_delete_preserves_original(self):
        source=self.model(); self.m.delete_model(source.name)
        self.assertTrue(source.exists()); self.assertFalse(self.m.installed())
    def test_duplicate_import_rejected(self):
        source=self.model()
        with self.assertRaises(ValueError): self.m.import_model(source)
    def test_html_import_rejected(self):
        source=self.root/'bad.gguf'; source.write_text('<html>bad</html>')
        with self.assertRaises(ValueError): self.m.import_model(source)
    def test_settings_range(self):
        self.m.config['port']=80
        with self.assertRaises(ValueError): self.m.save()
    def test_native_identity_and_loopback(self):
        self.model(); self.runtime(); cli=self.m.cli_args(); server=self.m.server_args()
        self.assertIn(prompt('നില'),cli)
        self.assertEqual(server[server.index('--host')+1],'127.0.0.1')
        self.assertNotIn('--tools',server)
        self.assertEqual(server[server.index('-ngl')+1],'0')
        ui=json.loads((self.m.home/'webui.json').read_text(encoding='utf-8'))
        self.assertEqual(ui['systemMessage'],prompt('നില')); self.assertFalse(ui['jsSandboxEnabled'])
    @patch('assistant.core.urlopen')
    def test_download_success(self,op):
        op.return_value=Response(GGUF); target=self.root/'a.gguf'
        download('https://example.org/a.gguf',target,gguf=True)
        self.assertEqual(target.read_bytes(),GGUF); self.assertFalse(list(self.root.glob('*.part')))
    @patch('assistant.core.urlopen')
    def test_truncated_download_cleanup(self,op):
        op.return_value=Response(GGUF,total=1000); target=self.root/'a.gguf'
        with self.assertRaises(OSError): download('https://example.org/a.gguf',target,gguf=True)
        self.assertFalse(target.exists()); self.assertFalse(list(self.root.glob('*.part')))
    @patch('assistant.core.urlopen')
    def test_checksum_preserves_existing(self,op):
        op.return_value=Response(b'bad'); target=self.root/'runtime.zip'; target.write_bytes(b'original')
        with self.assertRaises(ValueError): download('https://example.org/runtime.zip',target,sha256='0'*64)
        self.assertEqual(target.read_bytes(),b'original')
    @patch('assistant.core.urlopen')
    def test_cancel_cleanup(self,op):
        op.return_value=Response(GGUF); cancel=threading.Event(); cancel.set(); target=self.root/'a.gguf'
        with self.assertRaises(Cancelled): download('https://example.org/a.gguf',target,cancel=cancel)
        self.assertFalse(target.exists()); self.assertFalse(list(self.root.glob('*.part')))
    def test_zip_traversal(self):
        f=self.root/'bad.zip'
        with zipfile.ZipFile(f,'w') as z: z.writestr('../escape.exe',b'bad')
        with self.assertRaises(ValueError): safe_extract(f,self.root/'unpack')
        self.assertFalse((self.root/'escape.exe').exists())
    def test_delete_active_rejected(self):
        self.model(); self.m.process=Mock(); self.m.process.poll.return_value=None
        with self.assertRaises(ValueError): self.m.delete_model(self.m.config['model'])
    @patch('assistant.core.sys.platform', 'linux')
    def test_stop_cleanup(self):
        process=Mock(); process.poll.return_value=None; self.m.process=process
        self.m.log=io.StringIO(); log=self.m.log; self.m.stop()
        process.terminate.assert_called_once(); self.assertTrue(log.closed); self.assertIsNone(self.m.process)
    @patch('assistant.core.subprocess.Popen')
    def test_failed_server_cleanup(self,popen):
        self.model(); self.runtime(); proc=Mock(); proc.poll.return_value=1; popen.return_value=proc
        with self.assertRaises(RuntimeError): self.m.start_ui(lambda x:None)
        self.assertIsNone(self.m.process); self.assertIsNone(self.m.log)
if __name__=='__main__': unittest.main()
