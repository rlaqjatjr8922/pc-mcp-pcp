from remote.client import request
import os
def status():
    response=request('/system/status')['response']
    return {'connected':True,'transport':'webrtc-p2p','room':os.environ.get('PC_ROOM'),'base_url':'P2P / '+os.environ.get('PC_ROOM',''),'status':response.get('result',response)}
