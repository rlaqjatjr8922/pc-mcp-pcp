from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import config
from api import router, mcp, mcp_app
from remote_routes import router as remote_router
from control_ui import router as control_router
from fastapi.responses import RedirectResponse


@asynccontextmanager
async def lifespan(app):
    import asyncio,logging,os
    logger=logging.getLogger('pc_staff')
    async def connect():
        from remote.status import status
        announced=False
        while True:
            try:
                result=await asyncio.to_thread(status)
                logger.info('Customer P2P connection ready: %s',result.get('room'))
                print('Customer P2P connected.',flush=True)
                return
            except asyncio.CancelledError: raise
            except Exception as exc:
                logger.warning('P2P connection pending: %s',type(exc).__name__)
                if not announced:
                    print('Waiting for Worker / Customer connection. Retrying automatically.',flush=True)
                    announced=True
                await asyncio.sleep(3)
    import socket,subprocess,sys
    probe=socket.socket(); probe.settimeout(.2)
    proxy_running=probe.connect_ex(('127.0.0.1',8766))==0
    probe.close()
    proxy_process=None
    proxy_stdout=None
    proxy_stderr=None
    if not proxy_running:
        folder=config.DATA_DIR/'tunnel'; folder.mkdir(parents=True,exist_ok=True)
        proxy_stdout=(folder/'proxy.stdout.log').open('a',encoding='utf-8')
        proxy_stderr=(folder/'proxy.stderr.log').open('a',encoding='utf-8')
        proxy_process=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parent/'gpt_proxy.py')],stdout=proxy_stdout,stderr=proxy_stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (folder/'proxy.pid').write_text(str(proxy_process.pid),encoding='utf-8')
    async with mcp.session_manager.run():
        task=asyncio.create_task(connect()) if os.environ.get('PC_ROOM') and os.environ.get('PC_SHARED_KEY') else None
        try: yield
        finally:
            if proxy_process:
                proxy_process.terminate()
                await asyncio.to_thread(proxy_process.wait)
            if proxy_stdout: proxy_stdout.close()
            if proxy_stderr: proxy_stderr.close()
            if task:
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
            from remote.transport import transport
            if transport.pc:
                closing=asyncio.run_coroutine_threadsafe(transport.pc.close(),transport.loop)
                try: await asyncio.wrap_future(closing)
                except Exception: pass


app = FastAPI(
    lifespan=lifespan,
    title="PC Control Server",
    version="1.0.0"
)

app.include_router(router)
app.include_router(remote_router)
app.include_router(control_router)


@app.get("/")
def root():
    return RedirectResponse('/control')

@app.get('/health')
def health():
    return {'success': True, 'server': 'PC Control Server'}


# Mount last so existing HTTP routes retain priority.
app.mount("/", mcp_app)

