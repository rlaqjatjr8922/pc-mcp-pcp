"""SimSimPC JSON command server. Run: python server.py"""
import argparse
import importlib.util
import inspect
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
import uvicorn

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "cor"
CONFIG = ROOT / "config"
TOOLS = {}
SETTINGS = {}

def read_json(filename):
    with (CONFIG / filename).open(encoding="utf-8") as f:
        return json.load(f)

def load_settings():
    global SETTINGS
    SETTINGS = {
        "permissions": read_json("permissions.json"),
        "defaults": read_json("defaults.json"),
        "server": read_json("server.json"),
    }
    return SETTINGS

def discover_tools():
    """Register only files inside cor/, without running their main blocks."""
    TOOLS.clear()
    for path in sorted(CORE.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        name = path.relative_to(CORE).as_posix()
        try:
            spec = importlib.util.spec_from_file_location(
                "simsim_tool_" + name.replace("/", "_").replace(".", "_"), path
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not callable(getattr(mod, "run", None)):
                raise ValueError("run() missing")
            signature = inspect.signature(mod.run)
            required = [
                p.name for p in signature.parameters.values()
                if p.default is inspect.Parameter.empty
                and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
            ]
            TOOLS[name] = {"module": mod, "signature": signature, "required": required}
        except Exception as exc:
            print(f"[SKIP] {name}: {exc}")
    return list(TOOLS)

def execute(command, actor):
    """actor is authenticated server-side, NEVER trusted from command JSON."""
    if not isinstance(command, dict) or not isinstance(command.get("path"), str):
        return {"success": False, "error": "INVALID_REQUEST"}
    path = command["path"].replace("\\", "/")
    if path not in TOOLS:
        return {"success": False, "error": "UNKNOWN_TOOL", "path": path}
    permissions = SETTINGS["permissions"]
    if actor not in ("bot", "human"):
        return {"success": False, "error": "UNAUTHORIZED"}
    if path in permissions.get("disabled", []):
        return {"success": False, "error": "TOOL_DISABLED"}
    if actor == "bot" and path in permissions.get("bot_denied", []):
        return {"success": False, "error": "PERMISSION_DENIED"}
    params = command.get("params", {})
    if not isinstance(params, dict):
        return {"success": False, "error": "INVALID_PARAMS"}
    params = {**SETTINGS["defaults"].get(path, {}), **params}
    tool = TOOLS[path]
    missing = [name for name in tool["required"] if name not in params]
    if missing:
        return {"success": False, "error": "MISSING_PARAMETER", "missing": missing}
    try:
        bound = tool["signature"].bind(**params)
        return {"success": True, "result": tool["module"].run(*bound.args, **bound.kwargs)}
    except TypeError as exc:
        return {"success": False, "error": "INVALID_PARAMETER", "detail": str(exc)}
    except Exception as exc:
        return {"success": False, "error": "EXECUTION_FAILED", "detail": type(exc).__name__}

app = FastAPI(title="SimSimPC Control")

@app.get("/health")
def health():
    return {"success": True, "tools": len(TOOLS)}

@app.get("/tools")
def tools_list(request: Request):
    actor = authenticate(request)
    denied = set(SETTINGS["permissions"].get("disabled", []))
    if actor == "bot":
        denied.update(SETTINGS["permissions"].get("bot_denied", []))
    return {"tools": [{"path": k, "required": v["required"]} for k, v in TOOLS.items() if k not in denied]}

def authenticate(request):
    import hmac
    key = request.headers.get("X-API-Key", "")
    keys = SETTINGS["server"]["api_keys"]
    for actor in ("human", "bot"):
        if keys.get(actor) and hmac.compare_digest(key, keys[actor]):
            return actor
    raise HTTPException(401, "Invalid API key")

@app.post("/execute")
async def dispatch(request: Request):
    actor = authenticate(request)
    try:
        command = await request.json()
    except ValueError:
        raise HTTPException(400, "Invalid JSON")
    result = execute(command, actor)
    if not result["success"]:
        raise HTTPException(400, result)
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    load_settings()
    discover_tools()
    print(f"Registered {len(TOOLS)} tools")
    if args.list:
        print("\n".join(TOOLS))
    else:
        conf = SETTINGS["server"]
        if conf["api_keys"].get("human", "").startswith("CHANGE_ME") or conf["api_keys"].get("bot", "").startswith("CHANGE_ME"):
            raise SystemExit("Edit config/server.json: set distinct strong API keys first")
        uvicorn.run(app, host=conf.get("host", "127.0.0.1"), port=conf.get("port", 8765))
