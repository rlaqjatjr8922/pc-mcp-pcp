@echo off
cd /d "%~dp0"
set "PC_SERVER_TASK_ROOT=%~dp0"
powershell.exe -NoProfile -Command "$c=Join-Path $env:PC_SERVER_TASK_ROOT 'Customer'; $p=Join-Path $c 'server.py'; if (-not (Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%%'\" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($p) })) { $l=Join-Path $c 'dat\logs'; [IO.Directory]::CreateDirectory($l) | Out-Null; Start-Process -FilePath (Join-Path $c '.venv\Scripts\pythonw.exe') -ArgumentList ('"'+$p+'"') -WorkingDirectory $c -WindowStyle Hidden -RedirectStandardOutput (Join-Path $l 'hidden-client.stdout.log') -RedirectStandardError (Join-Path $l 'hidden-client.stderr.log') }; $s=Join-Path $env:PC_SERVER_TASK_ROOT 'Staff'; Start-Process -FilePath (Join-Path $s 'connect-gpt.bat') -ArgumentList '--background' -WorkingDirectory $s -WindowStyle Hidden"
exit /b
