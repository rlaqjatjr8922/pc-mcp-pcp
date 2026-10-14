"""Real localhost WebRTC integration; no public signaling or user files."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from aiohttp import web
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Staff'/'cor'/'_runtime'))
from remote.transport import Transport
class P2PTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_datachannel(self):
        queues={'controller':[],'target':[]}
        key='local-test-shared-key-123456789'
        joined=asyncio.Event()
        async def handler(request):
            action=request.match_info['action']
            body=await request.json() if request.method=='POST' else dict(request.query)
            if body.get('key')!=key: return web.json_response({},status=403)
            peer=body['peer']
            if action=='join':
                if peer=='target': joined.set()
                return web.json_response({'ok':True})
            if action=='send':
                destination='target' if peer=='controller' else 'controller'
                queues[destination].append({'payload':body['payload']}); return web.json_response({'ok':True})
            items=queues[peer]; queues[peer]=[]; return web.json_response({'messages':items})
        app=web.Application(); app.router.add_route('*','/rooms/{room}/{action}',handler)
        runner=web.AppRunner(app); await runner.setup(); site=web.TCPSite(runner,'127.0.0.1',0); await site.start()
        port=site._server.sockets[0].getsockname()[1]
        signal='http://127.0.0.1:'+str(port)
        runtime=tempfile.TemporaryDirectory(prefix='pc-customer-runtime-')
        env={**os.environ,'PC_RUNTIME_ROOT':runtime.name}
        process=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'Customer'/'server.py'),'--room','localtestroom','--key',key,'--signal',signal,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=env)
        transport=Transport()
        async def call(path,params={}):
            import uuid
            return await asyncio.to_thread(transport.request,'localtestroom',key,signal,{'id':uuid.uuid4().hex,'path':path,'params':params},30)
        try:
            await asyncio.wait_for(joined.wait(),20)
            status=await call('/system/status'); self.assertTrue(status['ok'],status)
            pc=transport.pc
            from datetime import datetime,timezone
            begin=datetime.now(timezone.utc).isoformat()
            status=await call('/system/status')
            end=datetime.now(timezone.utc).isoformat()
            macro=await call('/macro/create',{'title':'status replay test','start':begin,'end':end})
            self.assertTrue(macro['ok'],macro)
            macro_id=macro['response']['result']['id']
            replay=await call('/macro/run',{'macro_id':macro_id}); self.assertTrue(replay['ok'],replay)
            recording=await call('/recording/config',{}); self.assertTrue(recording['ok'],recording)
            shell=await call('/system/powershell_normal',{'command':"Write-Output 'pc-mcp-test'",'timeout':10})
            self.assertTrue(shell['ok'],shell)
            self.assertIn('pc-mcp-test',shell['response']['result']['stdout'])
            statuses=await asyncio.gather(call('/system/status'),call('/system/info'))
            self.assertTrue(all(result['ok'] for result in statuses),statuses)
            self.assertIs(transport.pc,pc)
            with tempfile.TemporaryDirectory(prefix='pc-mcp-test-') as folder:
                path=str(Path(folder)/'example.txt'); destination=str(Path(folder)/'copy.txt')
                watched=await call('/watch/start',{'condition':'file_exists','target':{'path':path},'options':{'interval':.05,'timeout':5}})
                self.assertTrue(watched['ok'],watched)
                watch_id=watched['response']['result']['watch_id']
                created=await call('/files/create',{'path':path,'content':{'text':'P2P test'}}); self.assertTrue(created['ok'],created)
                await asyncio.sleep(.1)
                matched=await call('/watch/status',{'watch_id':watch_id})
                self.assertTrue(matched['response']['result']['matched'],matched)
                copied=await call('/files/copy',{'path':path,'destination':destination}); self.assertTrue(copied['ok'],copied)
                read=await call('/files/read',{'path':destination}); self.assertEqual(read['response']['result']['content'],'P2P test')
            invalid=await call('/input/mouse',{'mode':'invalid'}); self.assertFalse(invalid['ok'])
            # Region-only image confirms binary transport without saving the full desktop.
            image=await call('/screen/screenshot',{'mode':'capture','target':{'region':{'x':0,'y':0,'width':32,'height':32}}})
            self.assertTrue(image['ok'],image); self.assertEqual(image['encoding'],'base64')
            marker=await call('/screen/marker',{'mode':'list','screenshot_id':image['screenshot_id']}); self.assertTrue(marker['ok'],marker)
            stopped=await call('/safety/kill_switch',{'reason':'integration test finished'})
            self.assertTrue(stopped['ok'],stopped)
            status=await call('/system/status')
            self.assertTrue(status['response']['result']['stopped'],status)
        finally:
            if transport.pc:
                future=asyncio.run_coroutine_threadsafe(transport.pc.close(),transport.loop)
                await asyncio.to_thread(future.result,10)
            transport.loop.call_soon_threadsafe(transport.loop.stop)
            if process.returncode is None: process.terminate()
            out,err=await process.communicate()
            await runner.cleanup()
            runtime.cleanup()
            if process.returncode not in (0,1,15): print(err.decode(errors='replace')[-1800:])
if __name__=='__main__': unittest.main()
