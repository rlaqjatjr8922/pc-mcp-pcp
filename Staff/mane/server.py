"""Staff HTTP / MCP server. Customer commands use WebRTC."""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    candidates=[ROOT/'.venv'/'Scripts'/'python.exe',ROOT.parent/'.venv'/'Scripts'/'python.exe',ROOT.parent/'Customer'/'.venv'/'Scripts'/'python.exe']
    if not importlib.util.find_spec('mcp'):
        import subprocess
        executable=next((path for path in candidates if path.is_file() and subprocess.run([str(path),'-c','import mcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0),None)
        if executable: raise SystemExit(subprocess.call([str(executable),str(Path(__file__).resolve()),*sys.argv[1:]]))
        raise SystemExit('Staff 실행 환경에 mcp가 필요합니다. Staff requirements.txt를 설치하세요.')
sys.path.insert(0,str(ROOT/'cor'/'_runtime'))
spec=importlib.util.spec_from_file_location('pc_control_service',ROOT/'cor'/'_runtime'/'service.py')
service=importlib.util.module_from_spec(spec); spec.loader.exec_module(service)
app=service.app
from starlette.routing import Mount
_mcp_mounts=[route for route in app.router.routes if isinstance(route,Mount)]
app.router.routes[:]=[route for route in app.router.routes if not isinstance(route,Mount)]
from fastapi import Request
from fastapi.responses import JSONResponse
import api
import config as runtime_config
import logging
from logging.handlers import RotatingFileHandler
_file_log=RotatingFileHandler(runtime_config.LOG_DIR/'server.log',maxBytes=2*1024*1024,backupCount=3,encoding='utf-8')
_file_log.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
logging.getLogger('pc_staff').addHandler(_file_log)
logging.getLogger('pc_staff').setLevel(logging.INFO)

def actor(request):
    import hmac
    settings=json.loads((ROOT/'config'/'server.json').read_text(encoding='utf-8'))
    incoming=request.headers.get('X-API-Key','')
    if incoming.lower().startswith('bearer '): incoming=incoming[7:]
    incoming=request.headers.get('authorization','').removeprefix('Bearer ') or incoming
    for role in ('human','bot'):
        expected=os.environ.get('PC_'+role.upper()+'_API_KEY',settings['api_keys'].get(role,''))
        if expected and not expected.startswith(('YOUR_','CHANGE_','REPLACE_')) and hmac.compare_digest(incoming,expected): return role
    return None

@app.middleware('http')
async def permissions(request, call_next):
    if request.url.path in ('/health','/','/control'): return await call_next(request)
    role=actor(request)
    if role is None: return JSONResponse({'success':False,'error':'UNAUTHORIZED'},401)
    policy=json.loads((ROOT/'config'/'permissions.json').read_text(encoding='utf-8'))
    denied=set(policy.get('disabled',[]))
    if role=='bot': denied.update(policy.get('bot_denied',[]))
    # MCP requests carry tool names in JSON; list results are filtered below.
    path=request.url.path.removeprefix('/mcp').strip('/')+'.py'
    if request.method=='POST' and request.url.path in ('/mcp','/control/call','/execute'):
        try:
            body=await request.json()
            if request.url.path=='/mcp': name=body.get('params',{}).get('name','')
            else: name=body.get('name','')
            if name and '_' in name: path=name.replace('_','/',1)+'.py'
            elif body.get('path'): path=body['path'].replace('\\','/')
        except (ValueError,AttributeError): pass
    if path in denied: return JSONResponse({'success':False,'error':'PERMISSION_DENIED'},403)
    request.state.actor=role
    from access_policy import denied_tools
    token=denied_tools.set(frozenset(denied))
    try: return await call_next(request)
    finally: denied_tools.reset(token)

@app.get('/tools')
async def listing(request:Request):
    policy=json.loads((ROOT/'config'/'permissions.json').read_text(encoding='utf-8'))
    denied=set(policy.get('disabled',[]))
    if request.state.actor=='bot': denied.update(policy.get('bot_denied',[]))
    return {'tools':[{'name':t.name,'path':t.name.replace('_','/',1)+'.py','schema':t.inputSchema} for t in await api.mcp.list_tools() if t.name.replace('_','/',1)+'.py' not in denied]}

@app.post('/execute')
async def dispatch(request:Request):
    try:
        body=await request.json()
        name=body.get('name') or body['path'].removesuffix('.py').replace('/','_',1)
        result=await api.mcp.call_tool(name,body.get('params',body.get('arguments',{})))
        return {'success':True,'result':result.structuredContent,'content_items':[c.model_dump(by_alias=True,exclude_none=True) for c in result.content]}
    except Exception as exc: return JSONResponse({'success':False,'error':str(exc)},400)

app.router.routes.extend(_mcp_mounts)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--list',action='store_true'); p.add_argument('--room'); p.add_argument('--key'); p.add_argument('--signal'); a=p.parse_args()
    for key,value in [('PC_ROOM',a.room),('PC_SHARED_KEY',a.key),('PC_SIGNAL',a.signal)]:
        if value: os.environ[key]=value
    if a.list:
        import asyncio
        print('\n'.join(t.name for t in asyncio.run(api.mcp.list_tools())))
    else:
        settings=runtime_config.read_server()
        os.environ.setdefault('PC_ROOM',settings.get('room',''))
        os.environ.setdefault('PC_SHARED_KEY',settings.get('shared_key',''))
        room,key=os.environ['PC_ROOM'],os.environ['PC_SHARED_KEY']
        if not 8<=len(room)<=80 or len(key)<16:
            raise SystemExit('Room must be 8-80 characters; shared key must be 16+ characters.')
        print('P2P signaling: '+runtime_config.signal_url(),flush=True)
        import uvicorn
        settings=json.loads((ROOT/'config'/'server.json').read_text(encoding='utf-8'))
        uvicorn.run(app,host=settings.get('host','127.0.0.1'),port=settings.get('port',8765))
