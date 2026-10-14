# PC Control Server prototype

This is an **HTTP JSON dispatcher prototype**. It does not yet integrate WebRTC, MCP transport, or the old PC-Measure feature set. The existing Cloudflare Worker signaling files remain unchanged.

## Layout
- `server.py`: loads JSON config, scans `cor/**/*.py`, registers callable `run()` functions, validates arguments, and returns JSON
- `cor/`: executable individual tools; each supports direct CLI execution
- `config/permissions.json`: disabled tools and bot-denied tools
- `config/defaults.json`: missing optional values
- `config/server.json`: listener and distinct API credentials; **replace placeholders before use**
- `dat/`: reserved for runtime data

## Run
```powershell
py -m pip install -r requirements.txt
py server.py --list
# Set strong different human/bot keys in config/server.json; don't commit real keys
py server.py
```

Example request (on the same PC):
```powershell
$headers = @{"X-API-Key"="YOUR_HUMAN_KEY"}
$body = @{path="system/status.py";params=@{}} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8765/execute -Method Post -Headers $headers -Body $body -ContentType "application/json"
```

Direct tool test: `py cor/system/status.py`

The JSON field `caller` does **not** grant permissions: identity is assigned by the matching API key. JSON `path` must exactly name a discovered tool. Bot access to file copy is denied by default; change policy if needed. Do not expose this prototype to the public Internet; connection approval, secure secret storage, rate limiting, audit logging, and WebRTC authorization are future work.
