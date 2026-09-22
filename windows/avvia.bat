@echo off
REM Avvia "Il Maggiordomo" su Windows.
REM
REM Perche' un file separato da avvia.sh: avvia.sh e' uno script POSIX (usa bash,
REM venv/bin/python e setsid). Su Windows non parte, e adattarlo con mille "if
REM windows" lo renderebbe illeggibile per entrambi. Le due versioni fanno la
REM stessa cosa, in modo diverso perche' diverso e' il sistema.
REM
REM La prima volta crea l'ambiente e installa le dipendenze; dopo riusa quello
REM che c'e'. La finestra resta aperta: chiuderla = fermare l'app.

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "VENV=%~dp0..\.venv-win"
set "PY=%VENV%\Scripts\python.exe"
set "APP=%~dp0.."

REM I dati stanno accanto al codice, come sul resto delle piattaforme.
REM Per tenerli altrove (un disco esterno, un backup) togli "REM" e cambia il
REM percorso. Attenzione: devono restare gli stessi a ogni avvio, altrimenti
REM l'app riparte vuota.
REM set "MAGGIORDOMO_DATA=D:\MaggiordomoDati"

echo.
echo  ============================================
echo   Il Maggiordomo
echo  ============================================
echo.

REM --- Python ---
where python >nul 2>nul
if errorlevel 1 (
  echo  Python non e' installato, o non e' nel PATH.
  echo.
  echo  Scaricalo da https://www.python.org/downloads/windows/
  echo  Durante l'installazione spunta "Add python.exe to PATH".
  echo  Poi richiudi questa finestra e riapri il file.
  echo.
  pause
  exit /b 1
)

REM --- ambiente ---
if not exist "%PY%" (
  echo  Prima volta: preparo l'ambiente ^(un minuto circa^)...
  python -m venv "%VENV%"
  if errorlevel 1 (
    echo  Non sono riuscito a creare l'ambiente.
    pause
    exit /b 1
  )
)

"%PY%" -c "import flask" >nul 2>nul
if errorlevel 1 (
  echo  Installo le dipendenze...
  "%PY%" -m pip install --quiet --upgrade pip
  "%PY%" -m pip install --quiet -r "%APP%\requirements.txt"
  if errorlevel 1 (
    echo  Installazione non riuscita. Controlla la connessione.
    pause
    exit /b 1
  )
)

REM --- chiave Azure (facoltativa) ---
REM La voce neurale e' l'unica cosa che si configura. Senza, la voce del sistema:
REM l'app funziona lo stesso.
REM
REM Dove mettere la chiave: NON in questo file. Il codice sta su GitHub, anche
REM questo file, e ci finirebbe anche la chiave. Si mette in `segreto.bat`, nella
REM stessa cartella: quel file e' escluso da git, quindi la chiave resta qui.
REM
REM Se `segreto.bat` non esiste ancora, puoi copiare `segreto.esempio.bat`.
REM
if exist "%~dp0segreto.bat" call "%~dp0segreto.bat"

if "%AZURE_SPEECH_KEY%"=="" (
  echo  Voce: quella del sistema
) else (
  echo  Voce neurale Azure attiva ^(area: %AZURE_SPEECH_REGION%^)
)

REM Ottiene l'indirizzo di rete: e' quello che usi dal telefono. Non serve
REM scriverlo a mano, e cambierebbe comunque se il router assegna un indirizzo
REM diverso al computer. Il calcolo sta in indirizzo.ps1, non qui: dentro un .bat
REM quel comando si romperebbe per via delle virgolette.
set "IP="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0indirizzo.ps1"`) do set "IP=%%i"

echo.
echo   Sul computer:   http://localhost:12000
if not "%IP%"=="" echo   Dal telefono:   http://%IP%:12000
echo.
echo   Per fermare l'app: chiudi questa finestra.
echo.
echo  ============================================
echo.

set "PORT=12000"
set "HOST=0.0.0.0"
"%PY%" "%APP%\app.py"

echo.
echo  L'app si e' fermata. Leggi qui sopra: se c'e' un errore, e' quello.
pause
