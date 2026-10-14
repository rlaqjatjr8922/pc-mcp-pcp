"""PC tool requests travel over WebRTC; signaling never carries commands."""
import base64
import os
from fastapi import HTTPException
import api_config
import capture_store
GROUPS = ('mouse','keyboard','window','system','files','temp','screen','verify','watch','interaction','safety','input','recording','macro')
ALLOWED_PATHS = frozenset('/'+g+'/'+f for g in GROUPS for f in getattr(api_config,g) if g+'_'+f not in getattr(api_config,'_mcp_excluded',set()))

def request(path, parameters=None, method='POST'):
    if path not in ALLOWED_PATHS or method not in ('GET','POST'):
        raise HTTPException(400, '등록되지 않은 원격 요청')
    if path == '/screen/screenshot' and (parameters or {}).get('mode') == 'read':
        try: return capture_store.lookup(parameters.get('screenshot_id'))
        except ValueError: pass
    from measure_tools import validated
    group,feature=path.strip('/').split('/')
    import config
    parameters=validated(getattr(api_config,group)[feature],config.defaults(path,parameters or {}),path)
    room, key = os.environ.get('PC_ROOM'), os.environ.get('PC_SHARED_KEY')
    if not room or not key:
        raise HTTPException(503, 'PC_ROOM / PC_SHARED_KEY를 설정하세요.')
    from remote.transport import transport
    signal = config.signal_url()
    import uuid
    ident = uuid.uuid4().hex
    try:
        reply = transport.request(room, key, signal, {'id': ident, 'path':path,'params':parameters or {}}, timeout=max(90,int((parameters or {}).get('timeout',60))+40) if path.startswith('/system/powershell') else 3600 if path=='/macro/run' else 90)
    except Exception as exc:
        raise HTTPException(502, 'WebRTC 연결 실패: '+type(exc).__name__) from None
    if reply.get('id') != ident: raise HTTPException(502, '응답 ID 불일치')
    if not reply.get('ok'): raise HTTPException(reply.get('status',502), reply.get('error','원격 실행 실패'))
    if reply.get('encoding') == 'base64':
        try: return capture_store.save(base64.b64decode(reply['data'],validate=True),reply['content_type'],reply.get('screenshot_id'))
        except (ValueError,KeyError): raise HTTPException(502,'잘못된 이미지 응답') from None
    return {'response':reply['response']}
