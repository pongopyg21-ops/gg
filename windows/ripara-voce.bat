@echo off
REM Corregge l'area della voce con un doppio clic, senza toccare la chiave.
REM
REM Il lavoro vero sta in `ripara_voce.py`: la modifica tocca una riga di un file
REM che contiene la chiave, e una riga scritta male la rovinerebbe. In Python si
REM legge, si sostituisce **solo** la riga dell'area e si riscrive — e si prova
REM davvero, come tutto il resto. Qui c'e' solo il doppio clic.
REM
REM Si usa Python dell'app (`.venv-win`) se c'e'; altrimenti quello di sistema.

setlocal
cd /d "%~dp0"

set "PY=%~dp0..\.venv-win\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0..\ripara_voce.py" %*

echo.
pause
