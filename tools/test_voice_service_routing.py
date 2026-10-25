"""Execute real router/render functions with fake inference, without model loading."""
import ast
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
import urllib

from test_voice_catalog import wav, info
from nebakov_voice_samples import line_reference

ROOT=Path(__file__).resolve().parent/'tts_service'

class Tensor:
    ndim=2;shape=(1,100);dtype='fake'
    @property
    def T(self):return self
    def detach(self):return self
    def cpu(self):return self
    def transpose(self,*args):return self
    def contiguous(self):return self
    def numpy(self):return []

class Model:
    sr=24000
    def __init__(self):self.prepared=[];self.spoken=[];self.conds=None
    def prepare_conditionals(self,path,**kw):self.conds=Path(path).name;self.prepared.append(self.conds)
    def generate(self,text,**kw):self.spoken.append(self.conds);return Tensor()

def definitions(name, namespace):
    namespace.setdefault('BaseHTTPRequestHandler',BaseHTTPRequestHandler)
    namespace.setdefault('print',lambda *a,**k:None)
    tree=ast.parse((ROOT/name).read_text())
    tree.body=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))]
    exec(compile(tree,name,'exec'),namespace)
    return namespace

class ServiceRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT.parent);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.voices=self.root/'tts/voices';self.voices.mkdir(parents=True)
        for name in ['guard1.wav','guards_new.wav']:wav(self.voices/name)
        self.conversations=self.root/'output/conversations';self.conversations.mkdir(parents=True)
        self.folder=self.conversations/'test';self.folder.mkdir()
        rows=[{'speaker':'Marek' if i%2 else 'Hertl','text':'hello'} for i in range(1,5)]
        (self.folder/'conversation.json').write_text(json.dumps({'lines':rows}))
        self.samples={'Marek':'guards_new.wav','Hertl':'guard1.wav'}
        self.sf=types.SimpleNamespace(info=info,write=lambda path,*a,**k:wav(Path(path),.1))
        stub=patch.dict('sys.modules',{'soundfile':self.sf});stub.start();self.addCleanup(stub.stop)
        torch=types.SimpleNamespace(inference_mode=nullcontext,zeros=lambda *a,**k:Tensor(),cat=lambda *a,**k:Tensor())
        self.model=Model()
        voices={s:{'turbo':'tts/voices/guard1.wav','reference':self.voices/'guard1.wav','exaggeration':.5,'cfg_weight':.3} for s in self.samples}
        self.namespace=dict(ROOT=self.root,CONVERSATIONS=self.conversations,VOICES=self.voices,
            CONFIG={'voices':voices},SETTINGS=voices,MODEL=self.model,CACHE={},VOICE_CACHE={},
            sf=self.sf,torch=torch,json=json,time=time,Path=Path,line_reference=line_reference)

    def test_turbo_switches_by_reference_identity_and_reuses_conditioning(self):
        ns=definitions('tts_turbo_worker.py',self.namespace)
        ns['render'](self.folder,self.samples)
        self.assertEqual(self.model.spoken,['guards_new.wav','guard1.wav']*2)
        self.assertEqual(self.model.prepared,['guards_new.wav','guard1.wav'])
        ns['render'](self.folder,self.samples)
        self.assertEqual(len(self.model.prepared),2)

    def router_handler(self, result):
        router=definitions('tts_router.py',dict(BaseHTTPRequestHandler=BaseHTTPRequestHandler,
            json=json,Path=Path,LOCK=threading.Lock(),urllib=urllib))
        router['config']=lambda:{'default_model':'turbo','workers':{'turbo':8767}}
        router['ensure_worker']=lambda model:None
        router['worker_url']=lambda model:'http://127.0.0.1:8767'
        router['request_json']=lambda *a,**k:result
        body=json.dumps({'conversation_folder':'test'}).encode()
        handler=router['Handler'].__new__(router['Handler'])
        handler.path='/render';handler.headers={'Content-Length':str(len(body))};handler.rfile=io.BytesIO(body)
        handler.statuses=[];handler.send_response=lambda status:handler.statuses.append(status)
        handler.send_header=lambda *a:None;handler.end_headers=lambda:None
        handler.wfile=io.BytesIO()
        return handler

    def test_disconnect_during_headers_never_replies_twice_or_rerenders(self):
        for error in [ConnectionResetError(10054,'reset'),ConnectionAbortedError(10053,'closed')]:
            handler=self.router_handler({'status':'ok'})
            def broken():raise error
            handler.end_headers=broken
            handler.do_POST()
            self.assertEqual(handler.statuses,[200])
            self.assertTrue(handler.close_connection)
            self.assertFalse(handler.reply(500,{'error':'second response'}))
            self.assertEqual(handler.statuses,[200])

    def test_disconnect_during_body_is_handled_without_server_error(self):
        handler=self.router_handler({'status':'ok'})
        class ClosedStream:
            def write(self,data):raise BrokenPipeError('client stopped')
        handler.wfile=ClosedStream();handler.do_POST()
        self.assertEqual(handler.statuses,[200]);self.assertTrue(handler.close_connection)

    def test_serialization_failure_still_returns_one_real_500(self):
        handler=self.router_handler({'not_json':object()});handler.do_POST()
        self.assertEqual(handler.statuses,[500])
        self.assertIn('error',json.loads(handler.wfile.getvalue()))

    def test_standard_switches_by_reference_identity_and_reuses_conditioning(self):
        ns=definitions('tts_standard_worker.py',self.namespace)
        ns['render'](self.folder,self.model,self.samples)
        self.assertEqual(self.model.spoken,['guards_new.wav','guard1.wav']*2)
        self.assertEqual(self.model.prepared,['guards_new.wav','guard1.wav'])

    def test_real_router_forwards_mapping_to_real_turbo_render(self):
        worker=definitions('tts_turbo_worker.py',self.namespace)
        requests=[]
        def request_json(url,body,**kwargs):
            requests.append(body)
            return {'status':'ok','audio':worker['render'](self.folder,body['voicesampleid'])}
        router=definitions('tts_router.py',dict(BaseHTTPRequestHandler=BaseHTTPRequestHandler,
            json=json,Path=Path,LOCK=threading.Lock(),urllib=urllib,
            config=lambda:{'default_model':'turbo','workers':{'turbo':8767}},
            ensure_worker=lambda model:None,worker_url=lambda model:'http://127.0.0.1:8767',
            request_json=request_json))
        # Preserve actual Handler.do_POST; substitute only transport/model boundaries.
        router['ensure_worker']=lambda model:None
        router['config']=lambda:{'default_model':'turbo','workers':{'turbo':8767}}
        router['worker_url']=lambda model:'http://127.0.0.1:8767'
        router['request_json']=request_json
        body=json.dumps({'conversation_folder':'test','voicesampleid':self.samples}).encode()
        handler=router['Handler'].__new__(router['Handler'])
        handler.path='/render';handler.headers={'Content-Length':str(len(body))};handler.rfile=io.BytesIO(body)
        replies=[];handler.reply=lambda status,document:replies.append((status,document))
        handler.do_POST()
        self.assertEqual(replies[0][0],200,replies)
        self.assertEqual(requests[0]['voicesampleid'],self.samples)
        self.assertEqual(self.model.spoken,['guards_new.wav','guard1.wav']*2)
