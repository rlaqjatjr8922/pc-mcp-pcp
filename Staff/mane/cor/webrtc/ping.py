"""Send a JSON ping to Customer over a WebRTC data channel.

Auto-registers as cor/webrtc/ping.py via Staff/server.py and can run directly.
No remote execution or device control is performed.
"""
import argparse
import asyncio
import json
import time
from urllib.parse import quote

DEFAULT_SIGNAL = "https://pc-mcp-pcp.gimbeomseognam5.workers.dev"

async def _exchange(room, key, signal, timeout, message):
    import aiohttp
    from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription

    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")
    if not (8 <= len(room) <= 80) or len(key) < 16:
        raise ValueError("room must have 8-80 chars and key at least 16 chars")

    pc = RTCPeerConnection(configuration=RTCConfiguration(
        iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]
    ))
    loop = asyncio.get_running_loop()
    response = loop.create_future()
    chunks = {}
    base = signal.rstrip("/") + "/rooms/" + quote(room, safe="")

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async def post(action, body):
            async with session.post(base + "/" + action, json={"peer": "controller", "key": key, **body}) as resp:
                data = await resp.json()
                if resp.status >= 400:
                    raise RuntimeError(f"{action}: HTTP {resp.status}: {data}")
                return data

        async def poll():
            async with session.get(base + "/poll", params={"peer": "controller", "key": key}) as resp:
                data = await resp.json()
                if resp.status >= 400:
                    raise RuntimeError(f"poll: HTTP {resp.status}: {data}")
                return data.get("messages", [])

        channel = pc.createDataChannel("json-test")

        @channel.on("open")
        def on_open():
            channel.send(json.dumps(message, ensure_ascii=False))

        @channel.on("message")
        def on_message(raw):
            try:
                obj = json.loads(raw)
                if not isinstance(obj, dict):
                    raise ValueError("JSON object expected")
                if 'chunk' in obj:
                    ident=obj['chunk']; total=obj['total']; index=obj['index']
                    if not isinstance(total,int) or not 1<=total<=12000 or not isinstance(index,int) or not 0<=index<total or not isinstance(obj.get('data'),str): raise ValueError('Invalid chunk')
                    entry=chunks.setdefault(ident,{'total':total,'parts':{},'size':0})
                    if entry['total']!=total: raise ValueError('Chunk count changed')
                    if index not in entry['parts']:
                        entry['size']+=len(obj['data'])
                        if entry['size']>64*1024*1024: raise ValueError('Response too large')
                        entry['parts'][index]=obj['data']
                    if len(entry['parts'])<total: return
                    obj=json.loads(''.join(entry['parts'][i] for i in range(total)))
                    del chunks[ident]
                if not response.done():
                    response.set_result(obj)
            except (TypeError, ValueError) as exc:
                if not response.done():
                    response.set_exception(exc)

        try:
            await post("join", {})
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            await post("send", {"payload": {"type": "offer", "sdp": pc.localDescription.sdp}})
            deadline = time.monotonic() + timeout
            while not response.done() and time.monotonic() < deadline:
                for item in await poll():
                    p = item.get("payload", {})
                    if p.get("type") == "answer":
                        await pc.setRemoteDescription(RTCSessionDescription(sdp=p["sdp"], type="answer"))
                if not response.done():
                    await asyncio.sleep(0.4)
            if not response.done():
                raise TimeoutError("No response; check Customer app, room/key and NAT/TURN")
            return await response
        finally:
            await pc.close()

def run(room: str, key: str, message: dict = None, signal: str = DEFAULT_SIGNAL, timeout: int = 90):
    """Blocking JSON ping tool, usable by Staff/server.py automatic registration."""
    if message is None:
        message = {"message": "a"}
    return asyncio.run(_exchange(room, key, signal, timeout, message))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--room", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--json", default='{"message":"a"}')
    parser.add_argument("--signal", default=DEFAULT_SIGNAL)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    print(json.dumps(run(args.room, args.key, json.loads(args.json), args.signal, args.timeout), ensure_ascii=False))
