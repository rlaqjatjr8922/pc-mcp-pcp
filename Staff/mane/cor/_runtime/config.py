from pathlib import Path
import json,os
BASE_DIR=Path(__file__).resolve().parents[2]
CORE_DIR=BASE_DIR/'cor'
CONFIG_DIR=BASE_DIR/'config'
DATA_DIR=BASE_DIR/'dat'
HISTORY_DIR=DATA_DIR/'history'
LOG_DIR=DATA_DIR/'logs'
PLUGINS_DIR=CORE_DIR/'_runtime'/'plugins'
DEFAULT_SIGNAL='https://pc-mcp-pcp.gimbeomseognam5.workers.dev'
def read_server():
    return json.loads((CONFIG_DIR/'server.json').read_text(encoding='utf-8'))
def signal_url():
    return os.environ.get('PC_SIGNAL') or read_server().get('signal_url',DEFAULT_SIGNAL)
def defaults(path,values):
    settings=json.loads((CONFIG_DIR/'defaults.json').read_text(encoding='utf-8'))
    supplied=settings.get(path.strip('/')+'.py',{})
    # Translate the original copy-demo setting to the PC-control options contract.
    supplied=dict(supplied)
    if 'overwrite' in supplied:
        supplied['options']={**supplied.get('options',{}),'overwrite':supplied.pop('overwrite')}
    merged={**supplied,**values}
    if isinstance(supplied.get('options'),dict) and isinstance(values.get('options',{}),dict):
        merged['options']={**supplied['options'],**values.get('options',{})}
    return merged
server=read_server()
paths={'history':HISTORY_DIR,'logs':LOG_DIR,'plugins':PLUGINS_DIR}
for path in (DATA_DIR,HISTORY_DIR,LOG_DIR): path.mkdir(parents=True,exist_ok=True)
