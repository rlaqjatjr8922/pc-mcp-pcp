from measure_tools import invoke
def run(command,timeout=60):
    return invoke('/system/powershell_admin',{'command':command,'timeout':timeout})
