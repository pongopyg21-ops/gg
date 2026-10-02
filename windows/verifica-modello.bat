@echo off
REM Verifica che il modello di casa (Ollama) sia pronto per l'app.
REM
REM E' il controllo da fare quando Ollama sembra a posto ma l'app continua a
REM usare le regole: separa le tre cause che danno lo stesso sintomo — Ollama
REM spento, modello non scaricato, interruttore spento.
REM
REM Il lavoro vero sta in modello.ps1: dentro un .bat virgolette e caratteri
REM speciali si sbagliano facilmente e l'errore non si vedrebbe. Qui si chiama
REM e basta. Non modifica niente e non tocca i segreti.

setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0modello.ps1" -Dettaglio
exit /b %ERRORLEVEL%
