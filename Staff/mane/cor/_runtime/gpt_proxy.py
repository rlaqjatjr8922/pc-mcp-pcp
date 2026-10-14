"""Loopback-only tunnel adapter; all MCP requests run as Staff's bot."""
import asyncio,json
from pathlib import Path
from aiohttp import web,ClientSession,ClientTimeout
ROOT=Path(__file__).resolve().parents[2]
async def main():
    async with ClientSession(timeout=ClientTimeout(total=3700)) as session:
        async def forward(request):
            if request.path.startswith('/.well-known/'):
                return web.json_response({'error':'not_found'},status=404)
            if request.path!='/mcp': return web.json_response({'error':'not_found'},status=404)
            key=json.loads((ROOT/'config'/'server.json').read_text(encoding='utf-8'))['api_keys']['bot']
            headers={'X-API-Key':key}
            for name in ('Accept','Content-Type','Mcp-Session-Id','Mcp-Protocol-Version'):
                if name in request.headers: headers[name]=request.headers[name]
            async with session.request(request.method,'http://127.0.0.1:8765/mcp',headers=headers,data=await request.read()) as result:
                return web.Response(body=await result.read(),status=result.status,headers={'Content-Type':result.headers.get('Content-Type','application/json')})
        app=web.Application(client_max_size=48*1024*1024)
        app.router.add_route('*','/{tail:.*}',forward)
        runner=web.AppRunner(app); await runner.setup()
        await web.TCPSite(runner,'127.0.0.1',8766).start()
        print('GPT MCP adapter ready on 127.0.0.1:8766',flush=True)
        try: await asyncio.Event().wait()
        finally: await runner.cleanup()
if __name__=='__main__': asyncio.run(main())
