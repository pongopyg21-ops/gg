@echo off
REM Attiva l'indirizzo pubblico stabile de Il Maggiordomo (Tailscale Funnel).
REM
REM Perche' un file separato da avvia.bat: questo si esegue una volta sola, per
REM attivare l'indirizzo. avvia.bat fa girare l'app, che e' un'altra cosa.
REM
REM Il lavoro vero sta in dominio.ps1: dentro un .bat certi comandi si rompono
REM per via delle virgolette, e l'errore non si vedrebbe. Qui si chiama e basta.

setlocal
cd /d "%~dp0"

echo.
echo  ============================================
echo   Indirizzo pubblico de Il Maggiordomo
echo  ============================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dominio.ps1"
set "ESITO=%ERRORLEVEL%"

echo  ============================================
echo.

if not "%ESITO%"=="0" (
  echo  Non e' andata a buon fine: leggi sopra.
) else (
  echo  L'app deve essere in esecuzione ^(avvia.bat^), poi apri
  echo  l'indirizzo mostrato qui sopra.
)

pause
exit /b %ESITO%
