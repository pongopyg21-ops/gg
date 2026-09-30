# Verifica in un colpo solo che l'app sia raggiungibile **da fuori casa**.
#
# Non modifica niente e non tocca i segreti: legge lo stato e dice cosa manca.
# E' il controllo da fare quando il tunnel sembra attivo ma il telefono non
# carica: separa le tre cause che si confondono fra loro — il tunnel, l'app
# spenta, e il freno ai tentativi che non riconosce i dispositivi.
#
# Perche' un .ps1 e non tutto dentro il .bat: dentro un .bat virgolette e
# caratteri speciali si sbagliano facilmente e l'errore non si vedrebbe.
# Qui il codice si legge e si prova.

$ErrorActionPreference = "Continue"

# La porta dell'app: quella dichiarata in avvia.bat, o 12000.
$Porta = if ($env:PORT) { $env:PORT } else { "12000" }

# tailscale.exe sta qui nell'installazione normale; se non c'e' (versione dallo
# Store, o percorso scelto a mano) si cerca nel PATH.
$Tailscale = "C:\Program Files\Tailscale\tailscale.exe"
if (-not (Test-Path $Tailscale)) {
    $cmd = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($cmd) { $Tailscale = $cmd.Source }
}

Write-Host ""
Write-Host "  ============================================"
Write-Host "   Verifica: l'app e' raggiungibile da fuori?"
Write-Host "  ============================================"

# --- 1. Il tunnel ---
Write-Host ""
Write-Host "  1. Indirizzo pubblico (Tailscale Funnel)"
$tsOk = $false
if (-not (Test-Path $Tailscale)) {
    Write-Host "     Tailscale non risulta installato."
    Write-Host "     Installalo da https://tailscale.com/download/windows"
    Write-Host "     e accedi; poi riprova."
} else {
    # Collegato? Se no, funnel non puo' fare nulla: dirlo adesso e' piu' utile
    # che mostrare l'errore di funnel, che non spiega la causa.
    & $Tailscale status *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "     Tailscale e' installato ma NON collegato."
        Write-Host "     Apri Tailscale dal menu Start e accedi, poi riprova."
    } else {
        $status = & $Tailscale funnel status 2>&1 | Out-String
        # L'indirizzo pubblico e' sempre https: cercarlo e' piu' affidabile del
        # codice di uscita, che cambia fra versioni di Tailscale. Quando Funnel
        # e' spento non compare nessun https.
        $url = [regex]::Match($status, 'https://[^\s]+').Value
        if ($url) {
            Write-Host "     Attivo: $url"
            Write-Host "     (inoltra su 127.0.0.1:$Porta)"
            $tsOk = $true
        } else {
            Write-Host "     Funnel NON attivo."
            Write-Host "     Attivalo con windows\dominio.bat (una volta sola)."
        }
    }
}

# --- 2. L'app in esecuzione ---
Write-Host ""
Write-Host "  2. L'app risponde?"
try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Porta/" -TimeoutSec 5
    Write-Host "     Si': HTTP $($r.StatusCode) su http://127.0.0.1:$Porta/"
    $appOk = $true
} catch {
    Write-Host "     NO: nessuna risposta su http://127.0.0.1:$Porta/"
    Write-Host "     Avviala con windows\avvia.bat e lascia la finestra aperta."
    Write-Host "     (Se il tunnel punta a una porta diversa, avvia.bat lo dice.)"
    $appOk = $false
}

# --- 3. Il tunnel e' un proxy: DIETRO_PROXY va dichiarato ---
Write-Host ""
Write-Host "  3. DIETRO_PROXY (il tunnel e' un proxy)"
$launcher = Join-Path $PSScriptRoot "avvia.bat"
$proxyOk = (Test-Path $launcher) -and
           (Select-String -Path $launcher -Pattern 'set "DIETRO_PROXY=1"' -Quiet)
if ($proxyOk) {
    Write-Host "     avvia.bat lo dichiara: il freno ai tentativi distingue i dispositivi."
} else {
    Write-Host "     NON dichiarato in avvia.bat."
    Write-Host "     Dietro il tunnel l'app vede l'indirizzo del proxy al posto di"
    Write-Host "     quello di chi bussa: il freno ai tentativi conterebbe tutti"
    Write-Host "     insieme, e chi sbaglia la password farebbe aspettare gli altri."
}

# --- Esito ---
Write-Host ""
Write-Host "  ============================================"
if ($tsOk -and $appOk) {
    Write-Host "   Dovresti poter accedere da fuori."
    Write-Host ""
    Write-Host "   Apri l'indirizzo https://...ts.net dal telefono, anche in"
    Write-Host "   un'altra rete (dati mobili): e' HTTPS, quindi funziona"
    Write-Host "   anche il microfono."
    Write-Host ""
    Write-Host "   La prima volta l'indirizzo puo' impiegare fino a dieci"
    Write-Host "   minuti a rispondere ovunque: e' la propagazione del nome."
} else {
    Write-Host "   Manca qualcosa: ogni punto qui sopra dice cosa fare."
}
Write-Host "  ============================================"
Write-Host ""

Read-Host "  Premi Invio per chiudere"
