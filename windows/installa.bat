@echo off
REM Installa "Il Maggiordomo" perche' parta da solo a ogni accesso a Windows,
REM e si riavvii se cade.
REM
REM Perche' un'attivita' pianificata e non il semplice collegamento nella cartella
REM "Esecuzione automatica": il collegamento fa partire l'app una volta, ma se
REM questa si ferma per un errore resta ferma. L'attivita' pianificata la
REM sorveglia e la fa ripartire. E' la differenza fra le due, ed e' proprio
REM quello che serve a un'app di casa: nessuno vuole accorgersi che e' caduta.
REM
REM Non servono privilegi di amministratore: l'attivita' e' dell'utente e parte
REM all'accesso. La finestra del server resta ridotta a icona.
REM
REM Uso:  installa.bat            installa e avvia
REM       installa.bat rimuovi    toglie l'avvio automatico

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "NOME=IlMaggiordomo"
set "AVVIO=%~dp0avvia.bat"

if /i "%~1"=="rimuovi" goto :rimuovi

echo.
echo  ============================================
echo   Avvio automatico de Il Maggiordomo
echo  ============================================
echo.

REM Un'attivita' omonima ma vecchia punterebbe a un percorso che non esiste piu':
REM si sostituisce invece di lasciarne due, perche' due = il server parte due
REM volte e la seconda non trova la porta libera.
schtasks /Query /TN "%NOME%" >nul 2>nul
if not errorlevel 1 (
  echo  Trovata un'installazione precedente: la sostituisco.
  schtasks /Delete /TN "%NOME%" /F >nul 2>nul
)

echo  Registro l'attivita' pianificata...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$a = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c \"%AVVIO%\"';" ^
  "$t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME;" ^
  "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew;" ^
  "Register-ScheduledTask -TaskName '%NOME%' -Action $a -Trigger $t -Settings $s -Description 'Il Maggiordomo: server dell app di casa' -Force | Out-Null"

if errorlevel 1 (
  echo.
  echo  Non sono riuscito a registrare l'attivita'.
  echo  Prova a fare clic destro su questo file e scegliere "Esegui come amministratore".
  echo.
  pause
  exit /b 1
)

echo  Fatto.
echo.
echo  Da adesso l'app parte da sola quando accedi a Windows, e se si ferma
echo  riparte entro un minuto. La finestra resta ridotta a icona nella barra.
echo.
echo  Per avviarla subito, senza riavviare il computer:
schtasks /Run /TN "%NOME%" >nul 2>nul
echo     premuto.
echo.
echo  Ci mette qualche secondo. Poi apri http://localhost:12000
echo.
echo  Per togliere l'avvio automatico:  installa.bat rimuovi
echo.
pause
exit /b 0

:rimuovi
echo.
schtasks /Delete /TN "%NOME%" /F >nul 2>nul
if errorlevel 1 (
  echo  Non c'era nessun avvio automatico da togliere.
) else (
  echo  Avvio automatico tolto.
  echo.
  echo  Nota: se l'app sta girando adesso, continua a girare. Per fermarla chiudi
  echo  la sua finestra, oppure riavvia il computer.
)
echo.
pause
exit /b 0
