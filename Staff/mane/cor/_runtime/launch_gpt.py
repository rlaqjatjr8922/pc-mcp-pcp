"""One-click Staff server + OpenAI tunnel launcher."""
import argparse,json,os,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
APP=ROOT/'mane'
PYTHON=APP/'.venv'/'Scripts'/'python.exe'
SERVER=APP/'server.py'
TUNNEL=ROOT/'tunnel-client.exe'
KEYFILE=ROOT/'api.txt'
DATA=APP/'dat'/'tunnel'

def listening(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=.3): return True
    except OSError: return False

def stop_owned_process(process):
    if process is None or process.poll() is not None: return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    else: process.terminate()
    try: process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill(); process.wait(timeout=2)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--check',action='store_true'); parser.add_argument('--background',action='store_true'); args=parser.parse_args()
    if args.background:
        DATA.mkdir(parents=True,exist_ok=True)
        sys.stdout=(DATA/('background-'+str(os.getpid())+'.stdout.log')).open('a',encoding='utf-8',buffering=1)
        sys.stderr=(DATA/('background-'+str(os.getpid())+'.stderr.log')).open('a',encoding='utf-8',buffering=1)
    for path in (PYTHON,SERVER,TUNNEL,KEYFILE):
        if not path.is_file(): raise RuntimeError('Required file missing: '+str(path))
    key=KEYFILE.read_text(encoding='utf-8-sig').strip()
    if not key: raise RuntimeError('api.txt is empty. Enter your OpenAI runtime API key there.')
    if args.check:
        print('Launcher files OK. Staff -> 8765, MCP adapter -> 8766, tunnel -> OpenAI.'); return 0
    import httpx
    DATA.mkdir(parents=True,exist_ok=True)
    owned_server=None; owned_tunnel=None; stdout=None; stderr=None
    try:
        if not listening(8765):
            stdout=(DATA/'staff.stdout.log').open('a',encoding='utf-8')
            stderr=(DATA/'staff.stderr.log').open('a',encoding='utf-8')
            owned_server=subprocess.Popen([str(PYTHON),str(SERVER)],cwd=APP,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            (DATA/'staff.pid').write_text(str(owned_server.pid),encoding='utf-8')
            print('Starting Staff server...',flush=True)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if owned_server and owned_server.poll() is not None: raise RuntimeError('Staff server stopped. Check mane/dat/tunnel/staff.stderr.log.')
            try:
                response=httpx.get('http://127.0.0.1:8765/health',timeout=1)
                tools=httpx.post('http://127.0.0.1:8766/mcp',headers={'Accept':'application/json, text/event-stream'},json={'jsonrpc':'2.0','id':1,'method':'tools/list'},timeout=2)
                if response.status_code==200 and tools.status_code==200 and 'result' in tools.json(): break
            except (httpx.HTTPError,ValueError): pass
            time.sleep(.3)
        else: raise RuntimeError('Staff/MCP did not become ready. Check mane/dat/tunnel logs.')
        print('Staff server and GPT MCP ready.',flush=True)
        if listening(8080):
            check=subprocess.run([str(TUNNEL),'health','--port','8080','--require-control-plane-poll','--json'],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if args.background else 0)
            if check.returncode==0:
                print('GPT tunnel is already connected.'); return 0
            raise RuntimeError('A tunnel is already running on port 8080. Close that tunnel window and run this file again.')
        result=subprocess.run([str(TUNNEL),'init','--sample','sample_mcp_remote_no_auth','--profile','pc-control','--profile-dir',str(DATA/'profiles'),'--tunnel-id','tunnel_6ab8f159ba288191966b64671bff3748','--mcp-server-url','http://127.0.0.1:8766/mcp','--force'],cwd=ROOT,stdout=sys.stdout,stderr=sys.stderr,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if args.background else 0)
        if result.returncode: return result.returncode
        env={**os.environ,'CONTROL_PLANE_API_KEY':key}
        print('Connecting GPT tunnel. Keep this window open; Ctrl+C stops it.',flush=True)
        owned_tunnel=subprocess.Popen([str(TUNNEL),'run','--profile','pc-control','--profile-dir',str(DATA/'profiles')],cwd=ROOT,env=env,stdout=sys.stdout,stderr=sys.stderr,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0) | (getattr(subprocess,'CREATE_NO_WINDOW',0) if args.background else 0))
        return owned_tunnel.wait()
    finally:
        # Ignore repeated Ctrl+C only while cleaning up processes we started.
        import signal
        previous=signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            stop_owned_process(owned_tunnel)
            stop_owned_process(owned_server)
        finally: signal.signal(signal.SIGINT,previous)
        if stdout: stdout.close()
        if stderr: stderr.close()

if __name__=='__main__':
    try: raise SystemExit(main())
    except KeyboardInterrupt: print('Stopped.'); raise SystemExit(0)
    except Exception as exc: print('ERROR: '+str(exc)); raise SystemExit(1)
