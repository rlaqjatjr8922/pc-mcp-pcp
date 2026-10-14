"""One persistent data channel, multiplexed by request ID; no action retries."""
import asyncio
import json
import threading
import time
from urllib.parse import quote

class Transport:
    def __init__(self):
        self.loop=asyncio.new_event_loop()
        self.thread=threading.Thread(target=self.loop.run_forever,daemon=True)
        self.thread.start(); self.pc=None; self.channel=None; self.pending={}; self.chunks={}; self.identity=None
        self.connect_lock=None
    def request(self,room,key,signal,message,timeout=90):
        future=asyncio.run_coroutine_threadsafe(self.exchange(room,key,signal,message,timeout),self.loop)
        try: return future.result(timeout+20)
        except BaseException:
            future.cancel(); raise
    async def connect(self,room,key,signal):
        import aiohttp
        from aiortc import RTCPeerConnection,RTCSessionDescription,RTCConfiguration,RTCIceServer
        if self.connect_lock is None: self.connect_lock=asyncio.Lock()
        async with self.connect_lock:
            identity=(room,key,signal)
            if self.channel and self.channel.readyState=='open' and self.identity==identity: return
            if not 8<=len(room)<=80 or len(key)<16: raise ValueError('Invalid room/key')
            if self.pc: await self.pc.close()
            self.identity=identity
            pc=RTCPeerConnection(configuration=RTCConfiguration(iceServers=[RTCIceServer(urls='stun:stun.l.google.com:19302')]))
            self.pc=pc; self.channel=pc.createDataChannel('pc-control')
            opened=asyncio.Event()
            @self.channel.on('open')
            def on_open(): opened.set()
            @self.channel.on('message')
            def on_message(raw):
                try:
                    obj=json.loads(raw)
                    if 'chunk' in obj:
                        ident=obj['chunk']; count=obj['total']; index=obj['index']
                        if not isinstance(count,int) or not 1<=count<=12000 or not isinstance(index,int) or not 0<=index<count: raise ValueError('Bad chunk')
                        entry=self.chunks.setdefault(ident,{'count':count,'parts':{},'size':0,'started':time.monotonic()})
                        if entry['count']!=count: raise ValueError('Chunk count changed')
                        if index not in entry['parts']:
                            entry['size']+=len(obj['data'])
                            if entry['size']>64*1024*1024: raise ValueError('Response too large')
                            entry['parts'][index]=obj['data']
                        if len(entry['parts'])<count: return
                        obj=json.loads(''.join(entry['parts'][n] for n in range(count))); del self.chunks[ident]
                    pending=self.pending.get(obj.get('id'))
                    if pending and not pending.done(): pending.set_result(obj)
                except (ValueError,KeyError,TypeError):
                    for pending in self.pending.values():
                        if not pending.done(): pending.set_exception(ValueError('Invalid remote response'))
            @pc.on('connectionstatechange')
            async def state():
                if pc.connectionState in ('closed','failed','disconnected'):
                    for pending in self.pending.values():
                        if not pending.done(): pending.set_exception(ConnectionError('Data channel closed; action was not retried'))
                    self.chunks.clear()
            base=signal.rstrip('/')+'/rooms/'+quote(room,safe='')
            try:
              async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async def post(action,body):
                    async with session.post(base+'/'+action,json={'peer':'controller','key':key,**body}) as r:
                        if r.status>=400: raise RuntimeError('Signaling HTTP '+str(r.status))
                await post('join',{})
                await pc.setLocalDescription(await pc.createOffer())
                await post('send',{'payload':{'type':'offer','sdp':pc.localDescription.sdp}})
                deadline=time.monotonic()+60
                while not opened.is_set():
                    if time.monotonic()>deadline: raise TimeoutError('Customer connection timed out')
                    async with session.get(base+'/poll',params={'peer':'controller','key':key}) as r:
                        if r.status>=400: raise RuntimeError('Signaling HTTP '+str(r.status))
                        messages=(await r.json()).get('messages',[])
                    for item in messages:
                        payload=item.get('payload',{})
                        if payload.get('type')=='answer' and pc.remoteDescription is None:
                            await pc.setRemoteDescription(RTCSessionDescription(sdp=payload['sdp'],type='answer'))
                    await asyncio.sleep(.2)
            except BaseException:
                await pc.close(); raise
    async def exchange(self,room,key,signal,message,timeout):
        await self.connect(room,key,signal)
        ident=message['id']; future=self.loop.create_future(); self.pending[ident]=future
        try:
            for transfer in list(self.chunks):
                if time.monotonic()-self.chunks[transfer]['started']>120: del self.chunks[transfer]
            self.channel.send(json.dumps(message,ensure_ascii=False))
            return await asyncio.wait_for(future,timeout)
        finally: self.pending.pop(ident,None)

transport=Transport()
