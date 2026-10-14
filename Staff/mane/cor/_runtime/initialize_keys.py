import json,secrets
from pathlib import Path
path=Path(__file__).resolve().parents[2]/'config'/'server.json'
settings=json.loads(path.read_text(encoding='utf-8'))
for role in ('human','bot'):
    value=settings['api_keys'].get(role,'')
    if not value or value.startswith(('YOUR_','CHANGE_','REPLACE_')): settings['api_keys'][role]=secrets.token_urlsafe(32)
path.write_text(json.dumps(settings,indent=2),encoding='utf-8')
print('API keys configured in Staff/config/server.json; existing keys preserved.')
