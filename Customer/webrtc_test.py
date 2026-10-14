"""Minimal WebRTC data-channel a -> b test. No remote PC control."""
import argparse
import asyncio
import json
import secrets
import time
from urllib.parse import quote

import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer

DEFAULT_SIGNAL = "https://pc-mcp-pcp.gimbeomseognam5.workers.dev"

async def main(role, room, key, signal, timeout):
    peer = "controller" if role == "staff" else "target"
    base = signal.rstrip("/") + "/rooms/" + quote(room, safe="")
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
    pc = RTCPeerConnection(configuration=config)
    finished = asyncio.Event()
    connected = asyncio.Event()

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async def post(action, payload):
            async with session.post(base + "/" + action, json={"peer": peer, "key": key, **payload}) as response:
                data = await response.json()
                if response.status >= 400:
                    raise RuntimeError(f"{action}: HTTP {response.status}: {data}")
                return data

        async def poll():
            async with session.get(base + "/poll", params={"peer": peer, "key": key}) as response:
                data = await response.json()
                if response.status >= 400:
                    raise RuntimeError(f"poll: HTTP {response.status}: {data}")
                return data.get("messages", [])

        def wire(channel):
            @channel.on("open")
            def opened():
                print("WebRTC connected", flush=True)
                connected.set()
                if role == "staff":
                    print("send: a", flush=True)
                    channel.send("a")

            @channel.on("message")
            def message(value):
                print("received:", value, flush=True)
                if role == "customer" and value == "a":
                    channel.send("b")
                    print("send: b", flush=True)
                    finished.set()
                elif role == "staff" and value == "b":
                    finished.set()

        @pc.on("datachannel")
        def on_datachannel(channel):
            wire(channel)

        await post("join", {})
        print(f"Joined room {room} as {peer}", flush=True)
        if role == "staff":
            channel = pc.createDataChannel("test")
            wire(channel)
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            await post("send", {"payload": {"type": "offer", "sdp": pc.localDescription.sdp}})

        deadline = time.monotonic() + timeout
        try:
            while not finished.is_set() and time.monotonic() < deadline:
                for item in await poll():
                    payload = item.get("payload", {})
                    typ = payload.get("type")
                    if typ == "offer" and role == "customer":
                        await pc.setRemoteDescription(RTCSessionDescription(sdp=payload["sdp"], type="offer"))
                        answer = await pc.createAnswer()
                        await pc.setLocalDescription(answer)
                        await post("send", {"payload": {"type": "answer", "sdp": pc.localDescription.sdp}})
                    elif typ == "answer" and role == "staff":
                        await pc.setRemoteDescription(RTCSessionDescription(sdp=payload["sdp"], type="answer"))
                if not finished.is_set():
                    await asyncio.sleep(0.5)
            if not finished.is_set():
                raise TimeoutError("No a/b exchange. Check room/key, signaling deployment, firewall, NAT/TURN.")
            print("PASS: a -> b", flush=True)
        finally:
            await pc.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--room", required=True, help="Same 8-80 character room on both PCs")
    parser.add_argument("--key", required=True, help="Same shared secret of at least 16 characters")
    parser.add_argument("--signal", default=DEFAULT_SIGNAL)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    if not (8 <= len(args.room) <= 80) or len(args.key) < 16:
        parser.error("room must be 8-80 characters; key must be >=16 characters")
    asyncio.run(main("customer", args.room, args.key, args.signal, args.timeout))
