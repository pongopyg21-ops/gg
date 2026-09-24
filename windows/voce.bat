@echo off
REM Chiede la chiave della voce neurale e la scrive in `segreto.bat`.
REM
REM Perche' esiste questo file: `segreto.bat` deve contenere esattamente due righe,
REM con le virgolette al posto giusto e l'area in minuscolo. Scritto a mano e' facile
REM sbagliare, e un errore non da' un messaggio chiaro: la voce resta quella del
REM sistema e sembra che la chiave non funzioni. Qui la forma la sceglie il programma.
REM
REM La chiave si scrive in `segreto.bat` e non in `avvia.bat` perche' `avvia.bat` sta
REM su GitHub, che e' pubblico: la chiave finirebbe online. `segreto.bat` e' escluso,
REM quindi resta su questo computer.

setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Voce neurale - Il Maggiordomo

echo.
echo  ==========================================================
echo   Voce neurale - Il Maggiordomo
echo  ==========================================================
echo.
echo  Questo programma scrive la chiave Azure nel file giusto:
echo  non devi creare ne' modificare niente a mano.
echo.
echo  Ti servono due cose, dalla pagina "Chiavi ed endpoint"
echo  della tua risorsa Speech su portal.azure.com:
echo.
echo    1. la chiave (Chiave 1 o Chiave 2)
echo    2. l'area, per esempio italynorth
echo.
echo  ----------------------------------------------------------
echo.

if exist "segreto.bat" (
  echo  Nota: esiste gia' un segreto.bat e verra' sostituito.
  echo.
)

:chiedi
set "CHIAVE="
set /p "CHIAVE= Incolla la chiave e premi Invio: "
if "!CHIAVE!"=="" (
  echo.
  echo  Non hai incollato niente. Riprovo.
  echo.
  goto :chiedi
)
REM virgolette incollate per sbaglio romperebbero la riga: si tolgono
set "CHIAVE=!CHIAVE:"=!"

echo.
set "AREA="
set /p "AREA= Area [invio per italynorth]: "
if "!AREA!"=="" set "AREA=italynorth"
set "AREA=!AREA:"=!"
set "AREA=!AREA: =!"
REM l'area e' l'indirizzo del servizio: va minuscola, o l'indirizzo non esiste.
REM PowerShell fa il lavoro in un colpo, senza i giri che servirebbero in batch.
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "Write-Output ('!AREA!'.ToLower())"`) do set "AREA=%%a"

REM lunghezza della chiave, per far vedere che il copia-incolla e' completo
set "L=0"
set "TMP=!CHIAVE!"
:ciclo
if "!TMP!"=="" goto :fine_ciclo
set "TMP=!TMP:~1!"
set /a L+=1
goto :ciclo
:fine_ciclo

echo.
echo  ----------------------------------------------------------
echo   Controlla prima di salvare:
echo.
echo    chiave : comincia con !CHIAVE:~0,4!... e ha !L! caratteri
echo    area   : !AREA!
echo  ----------------------------------------------------------
echo.

set "CONFERMA="
set /p "CONFERMA= E' giusto? Scrivi S per salvare, N per rifare: "
if /i not "!CONFERMA!"=="S" goto :chiedi

(
  echo @echo off
  echo REM Chiave della voce neurale. Generato da voce.bat.
  echo set "AZURE_SPEECH_KEY=!CHIAVE!"
  echo set "AZURE_SPEECH_REGION=!AREA!"
) > "segreto.bat"

echo.
echo  Fatto: segreto.bat e' pronto in questa cartella.
echo.
echo  Ora chiudi questa finestra, riapri avvia.bat, e controlla
echo  che all'avvio compaia:
echo.
echo     Voce neurale Azure attiva ^(area: !AREA!^)
echo.
echo  Se invece leggi "Voce: quella del sistema", la chiave o
echo  l'area non sono giuste: rilancia voce.bat e rifai.
echo.
pause
exit /b 0
