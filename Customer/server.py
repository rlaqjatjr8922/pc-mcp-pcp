"""Explicitly launched Customer agent; commands remain on the P2P data channel."""
import argparse
import asyncio
import base64
import importlib.util
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parent
# VS Code may launch a different Python. Use the installed Customer environment
# before loading any third-party dependencies, preserving arguments and stdin.
if __name__ == '__main__':
    local_python=ROOT/'.venv'/'Scripts'/'python.exe'
    if Path(sys.prefix).resolve() != (ROOT/'.venv').resolve():
        if not local_python.is_file():
            raise SystemExit('Customer 실행 환경이 없습니다. Customer 폴더의 setup.ps1을 먼저 실행하세요.')
        import subprocess
        raise SystemExit(subprocess.call([str(local_python),str(Path(__file__).resolve()),*sys.argv[1:]]))
sys.path.insert(0,str(ROOT/'cor'/'_runtime'))
spec=importlib.util.spec_from_file_location('customer_engine',ROOT/'cor'/'_runtime'/'service.py')
engine=importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
sys.modules["server"]=engine
sys.path.insert(0,str(ROOT/"cor"))
import api_config
import config
ALLOWED={('/'+g+'/'+f) for g in ('mouse','keyboard','window','system','files','temp','screen','verify','watch','interaction','safety','input','recording','macro') for f in getattr(api_config,g) if g+'_'+f not in getattr(api_config,'_mcp_excluded',set())}

def normalize(path, params):
    if path not in ALLOWED or not isinstance(params,dict): raise ValueError('Invalid tool or parameters')
    if config.disabled(path): raise PermissionError('TOOL_DISABLED')
    group,feature=path.strip('/').split('/')
    from request_schema import validated
    return group,feature,validated(getattr(api_config,group)[feature],config.defaults(path,params),path)

async def execute_message(raw):
    ident=None
    try:
        body=json.loads(raw)
        if not isinstance(body,dict): raise ValueError('JSON object required')
        ident=body.get('id')
        if body=={'message':'a'}: return {'message':'b'}
        group,feature,params=normalize(body.get('path'),body.get('params',{}))
        import httpx
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=engine.app),base_url='http://customer') as client:
            response=await client.post('/'+group+'/'+feature,json=params)
        if response.status_code>=400: return {'id':ident,'ok':False,'status':response.status_code,'error':response.json().get('error','Failed')}
        if response.headers.get('content-type','').startswith('image/'):
            from screen.screenshot import _uid,_save,_timestamp,_image_hash
            from PIL import Image
            from io import BytesIO
            screenshot_id=_uid()
            folder=config.DATA_DIR/'screenshots'; folder.mkdir(parents=True,exist_ok=True)
            (folder/(screenshot_id+'.png')).write_bytes(response.content)
            with Image.open(BytesIO(response.content)) as image: width,height=image.size
            _save('screenshot',{'id':screenshot_id,'area':{'left':0,'top':0,'width':width,'height':height},'target':params.get('target',{}),'created_at':_timestamp(),'hash':_image_hash(response.content)})
            return {'id':ident,'screenshot_id':screenshot_id,'ok':True,'encoding':'base64' ,'content_type':response.headers['content-type'],'data':base64.b64encode(response.content).decode()}
        return {'id':ident,'ok':True,'response':response.json()}
    except PermissionError as exc: return {'id':ident,'ok':False,'status':403,'error':str(exc)}
    except Exception as exc: return {'id':ident,'ok':False,'status':400,'error':str(exc)}

async def main(room,key,signal,timeout=0):
    import aiohttp
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
    if not 8<=len(room)<=80 or len(key)<16: raise ValueError('Invalid room / key')
    base=signal.rstrip('/')+'/rooms/'+quote(room,safe='')
    peers=set(); tasks=set()
    async with engine.app.router.lifespan_context(engine.app):
      async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async def post(action,body):
            async with session.post(base+'/'+action,json={'peer':'target','key':key,**body}) as r:
                if r.status>=400: raise RuntimeError('Signaling HTTP '+str(r.status))
                return await r.json()
        await post('join',{})
        print('Customer PC control active. Ctrl+C to stop.',flush=True)
        start=time.monotonic()
        try:
          while not timeout or time.monotonic()-start<timeout:
            async with session.get(base+'/poll',params={'peer':'target','key':key}) as r:
                if r.status>=400: raise RuntimeError('Signaling HTTP '+str(r.status))
                messages=(await r.json()).get('messages',[])
            for item in messages:
                payload=item.get('payload',{})
                if payload.get('type')!='offer': continue
                pc=RTCPeerConnection(configuration=RTCConfiguration(iceServers=[RTCIceServer(urls='stun:stun.l.google.com:19302')]))
                peers.add(pc)
                @pc.on('connectionstatechange')
                async def state(pc=pc):
                    if pc.connectionState in ('failed','closed','disconnected'):
                        peers.discard(pc)
                        if pc.connectionState!='closed': await pc.close()
                @pc.on('datachannel')
                def channel_open(channel):
                    @channel.on('message')
                    def message(raw):
                        async def reply():
                            result=json.dumps(await execute_message(raw),ensure_ascii=False)
                            # SCTP messages are chunked so full-size screenshots work too.
                            size=48000
                            if len(result.encode('utf-8'))<=size: channel.send(result)
                            else:
                                import uuid
                                transfer=uuid.uuid4().hex
                                parts=[result[i:i+size//4] for i in range(0,len(result),size//4)]
                                for n,part in enumerate(parts):
                                    while channel.bufferedAmount>1024*1024: await asyncio.sleep(.02)
                                    if channel.readyState!='open': return
                                    channel.send(json.dumps({'chunk':transfer,'index':n,'total':len(parts),'data':part},ensure_ascii=False))
                        task=asyncio.create_task(reply()); tasks.add(task); task.add_done_callback(tasks.discard)
                await pc.setRemoteDescription(RTCSessionDescription(sdp=payload['sdp'],type='offer'))
                await pc.setLocalDescription(await pc.createAnswer())
                await post('send',{'payload':{'type':'answer','sdp':pc.localDescription.sdp}})
            await asyncio.sleep(.4)
        finally:
            for task in tasks: task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            await asyncio.gather(*(pc.close() for pc in peers))

if __name__=='__main__':
    import os,getpass,logging
    from logging.handlers import RotatingFileHandler
    settings=config.read_settings('server.json')
    p=argparse.ArgumentParser()
    p.add_argument('--list',action='store_true')
    p.add_argument('--room',default=os.environ.get('PC_ROOM') or settings.get('room'))
    p.add_argument('--key',default=os.environ.get('PC_SHARED_KEY') or settings.get('shared_key'))
    p.add_argument('--signal',default=os.environ.get('PC_SIGNAL') or settings.get('signal_url',config.DEFAULT_SIGNAL))
    p.add_argument('--timeout',type=int,default=0)
    args=p.parse_args()
    if args.list:
        print('\n'.join(sorted(path.strip('/').replace('/','_',1) for path in ALLOWED)))
    else:
        room=args.room
        key=args.key
        if not room or not key: raise SystemExit('config/server.json에 room과 shared_key가 필요합니다.')
        handler=RotatingFileHandler(config.DATA_DIR/'logs'/'server.log',maxBytes=2*1024*1024,backupCount=3,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.WARNING)
        print('P2P signaling: '+args.signal,flush=True)
        try: asyncio.run(main(room,key,args.signal,args.timeout))
        except KeyboardInterrupt: print('Customer stopped.')
