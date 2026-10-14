import asyncio
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Staff'))
import server
os.environ['PC_HUMAN_API_KEY']='test-human-api-key-123456789'
os.environ['PC_BOT_API_KEY']='test-bot-api-key-123456789'
class StaffTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(server.app)
        self.human={'X-API-Key':os.environ['PC_HUMAN_API_KEY']}
        self.bot={'X-API-Key':os.environ['PC_BOT_API_KEY']}
    def test_registry(self):
        tools=asyncio.run(server.api.mcp.list_tools())
        self.assertEqual(len(tools),81)
        for tool in tools:
            group,feature=tool.name.split('_',1)
            self.assertTrue((ROOT/'Staff'/'cor'/group/(feature+'.py')).is_file())
    def test_authentication(self):
        self.assertEqual(self.client.get('/tools').status_code,401)
        self.assertEqual(len(self.client.get('/tools',headers=self.human).json()['tools']),81)
    def test_permission(self):
        self.assertEqual(self.client.post('/execute',headers=self.bot,json={'path':'files/copy.py','params':{}}).status_code,403)
        self.assertEqual(self.client.post('/files/copy',headers=self.bot,json={}).status_code,403)
        listed=self.client.get('/control/tools',headers=self.bot).json()['tools']
        self.assertNotIn('files_copy',[t['name'] for t in listed])
    def test_mode_validation(self):
        result=self.client.post('/execute',headers=self.human,json={'name':'screen_capture','params':{'mode':'invalid'}})
        self.assertEqual(result.status_code,400)
    def test_browser(self):
        self.assertEqual(self.client.get('/control').status_code,200)
    def test_local_history(self):
        result=self.client.post('/execute',headers=self.human,json={'name':'history_list','params':{}})
        self.assertEqual(result.status_code,200,result.text)
    def test_mcp_http(self):
        with TestClient(server.app,base_url='http://127.0.0.1:8765') as client:
            headers={**self.human,'Accept':'application/json, text/event-stream'}
            result=client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(len(result.json()['result']['tools']),81)
            result=client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'history_list','arguments':{}}})
            self.assertEqual(result.status_code,200,result.text)
            self.assertFalse(result.json()['result'].get('isError'),result.text)
            result=client.post('/mcp',headers={**self.bot,'Accept':'application/json, text/event-stream'},json={'jsonrpc':'2.0','id':3,'method':'tools/list'})
            self.assertNotIn('files_copy',[tool['name'] for tool in result.json()['result']['tools']])
    def test_staff_structure(self):
        import config,capture_store
        self.assertEqual(config.DATA_DIR,ROOT/'Staff'/'dat')
        self.assertTrue(capture_store.folder().is_relative_to(config.DATA_DIR))
        self.assertEqual(config.signal_url(),'https://pc-mcp-pcp.gimbeomseognam5.workers.dev')
        self.assertFalse((ROOT/'Staff'/'control').exists())
        self.assertEqual(config.defaults('/files/copy',{})['options']['overwrite'],False)
        self.assertTrue(config.defaults('/files/copy',{'options':{'overwrite':True}})['options']['overwrite'])
    def test_parameter_contracts(self):
        from measure_tools import validated
        import api_config
        count=0
        for group in ('mouse','keyboard','window','system','files','temp','screen','verify','watch','interaction','safety','input','recording','macro'):
            for feature,params in getattr(api_config,group).items():
                if 'mode' in params:
                    for mode,fields in params['mode'].items():
                        # Every required field must be rejected when omitted.
                        if any(v is ... for v in fields.values()):
                            with self.assertRaises(ValueError): validated(params,{'mode':mode},'/'+group+'/'+feature)
                        else: validated(params,{'mode':mode},'/'+group+'/'+feature)
                        count+=1
                else:
                    if any(v is ... for v in params.values()):
                        with self.assertRaises(ValueError): validated(params,{},'/'+group+'/'+feature)
                    else: validated(params,{},'/'+group+'/'+feature)
                    count+=1
        self.assertGreater(count,80)
if __name__=='__main__': unittest.main()
