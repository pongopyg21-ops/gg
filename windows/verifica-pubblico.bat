@echo off
REM Verifica che l'app sia raggiungibile da fuori casa.
REM
REM Il lavoro vero sta in verifica-pubblico.ps1: dentro un .bat virgolette e
REM caratteri speciali si sbagliano facilmente e l'errore non si vedrebbe.
REM Qui si chiama e basta. Non modifica niente e non tocca i segreti.

setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verifica-pubblico.ps1"
exit /b %ERRORLEVEL%
