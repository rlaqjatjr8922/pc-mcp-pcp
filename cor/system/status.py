"""Safe starter tool, callable through the server or directly."""
import json
import platform
import socket

def run():
    return {"hostname": socket.gethostname(), "os": platform.system(), "release": platform.release()}

if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
