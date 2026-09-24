@echo off
REM Fa entrare di nuovo quando la password della casa e' persa.
REM
REM La password non si recupera - nel registro c'e' solo l'impronta - ma si puo'
REM sostituire con una nuova. Per farlo basta avere i file, che sono su questo
REM computer: e' il motivo per cui non serve la password vecchia.
REM
REM Non tocca i dati: cambia una riga nel registro e basta.

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "VENV=%~dp0..\.venv-win"
set "PY=%VENV%\Scripts\python.exe"
set "APP=%~dp0.."

title Password della casa - Il Maggiordomo
color 07

echo.
echo  ==========================================================
echo   Password della casa - Il Maggiordomo
echo  ==========================================================
echo.

if not exist "%PY%" (
  echo  Prima devi avviare l'app almeno una volta: apri avvia.bat.
  echo  Serve a preparare l'ambiente, un minuto circa.
  echo.
  pause
  exit /b 1
)

"%PY%" "%APP%\ripristina_password.py"
if errorlevel 1 (
  echo.
  echo  Non ho potuto completare. Il messaggio qui sopra dice perche'.
  echo.
)
pause
