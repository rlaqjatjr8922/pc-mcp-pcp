from system.powershell import run as _run
def run(command,timeout=60):
    return _run(command,privilege='normal',timeout=timeout)
