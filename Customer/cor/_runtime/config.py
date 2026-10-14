from pathlib import Path
from threading import RLock,Event
import json,os,time
BASE_DIR=Path(__file__).resolve().parents[2]
CORE_DIR=BASE_DIR/'cor'
CONFIG_DIR=BASE_DIR/'config'
RUNTIME_ROOT=Path(os.environ.get('PC_RUNTIME_ROOT',str(BASE_DIR)))
DATA_DIR=RUNTIME_ROOT/'dat'
PRIVATE=DATA_DIR/'state'
DB=PRIVATE/'feature-state.sqlite3'
HOST='127.0.0.1'
PORT=8010
screen={'selected_monitor':1}
KILL_SWITCH=False
lock=RLock(); input_lock=RLock(); stop_event=Event()
held_keys=set(); held_buttons=set(); started=time.monotonic()
BYPASS_HITL=False
stats={'requests':0,'errors':0,'duration_ms':0.0}
DEFAULT_SIGNAL='https://pc-mcp-pcp.gimbeomseognam5.workers.dev'
def read_settings(name):
    return json.loads((CONFIG_DIR/name).read_text(encoding='utf-8'))
def defaults(path,params):
    value=read_settings('defaults.json').get(path.strip('/')+'.py',{})
    return {**value,**params}
def disabled(path):
    return path.strip('/')+'.py' in read_settings('permissions.json').get('disabled',[])
for directory in (DATA_DIR,PRIVATE,DATA_DIR/'logs',DATA_DIR/'tmp'): directory.mkdir(parents=True,exist_ok=True)
