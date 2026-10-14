"""Customer CMD WebRTC JSON responder. Only a -> b ping, no PC-control."""
import argparse
import asyncio
import json
import time
from urllib.parse import quote

import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer

DEFAULT_SIGNAL = "https://pc-mcp-pcp.gimbeomseognam5.workers.dev"

async def main(room, key, signal, timeout):
    if not (8 <= len(room) <= 80) or len(key) < 16:
        raise ValueError("Invalid room or key")
    pc = RTCPeerConnection(configuration=RTCConfiguration(
        iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]
    ))
    done = asyncio.Event()
    base = signal.rstrip("/") + "/rooms/" + quote(room, safe="")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async def post(action, body):
            async with session.post(base + "/" + action, json={"peer": "target", "key": key, **body}) as resp:
                data = await resp.json()
                if resp.status >= 400:
                    raise RuntimeError(f"{action}: HTTP {resp.status}: {data}")
                return data

        async def poll():
            async with session.get(base + "/poll", params={"peer": "target", "key": key}) as resp:
                data = await resp.json()
                if resp.status >= 400:
                    raise RuntimeError(f"poll: HTTP {resp.status}: {data}")
                return data.get("messages", [])

        @pc.on("datachannel")
        def on_channel(channel):
            @channel.on("message")
            def on_message(raw):
                try:
                    request = json.loads(raw)
                    if not isinstance(request, dict):
                        raise ValueError("JSON object required")
                    value = request.get("message")
                    print("received JSON:", request, flush=True)
                    reply = {"message": "b"} if value == "a" else {
                        "success": False, "error": "UNKNOWN_MESSAGE"
                    }
                except (ValueError, TypeError):
                    reply = {"success": False, "error": "INVALID_JSON"}
                channel.send(json.dumps(reply, ensure_ascii=False))
                done.set()

        await post("join", {})
        print("Waiting for Staff JSON...", flush=True)
        try:
            deadline = time.monotonic() + timeout
            while not done.is_set() and time.monotonic() < deadline:
                for item in await poll():
                    p = item.get("payload", {})
                    if p.get("type") == "offer":
                        await pc.setRemoteDescription(RTCSessionDescription(sdp=p["sdp"], type="offer"))
                        answer = await pc.createAnswer()
                        await pc.setLocalDescription(answer)
                        await post("send", {"payload": {"type": "answer", "sdp": pc.localDescription.sdp}})
                if not done.is_set():
                    await asyncio.sleep(0.4)
            if not done.is_set():
                raise TimeoutError("No JSON message received")
            await asyncio.sleep(0.7)
        finally:
            await pc.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--room", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--signal", default=DEFAULT_SIGNAL)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    asyncio.run(main(args.room, args.key, args.signal, args.timeout))
