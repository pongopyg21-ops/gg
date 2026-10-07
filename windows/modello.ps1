# Dice se il modello di casa (Ollama) e' pronto: se risponde, se il modello che
# l'app si aspetta e' stato scaricato, e cosa fare se no.
#
# Da quando la comprensione col modello e' **sempre attiva** (non c'e' piu' un
# interruttore), le cause del "il modello non capisce" sono due e si confondono
# fra loro: Ollama spento e modello diverso da quello atteso. Questo file le
# separa. Prima ce n'era una terza — l'interruttore in Profilo > Capire i
# comandi — che non esiste piu'.
#
# Perche' un .ps1 e non dentro avvia.bat: dentro un .bat virgolette e caratteri
# speciali si sbagliano facilmente e l'errore non si vedrebbe. E la
# configurazione si **chiede all'app** (`comprensione`), invece di riscriverla
# qui: due copie della stessa regola divergono, e allora lo stato all'avvio
# mente — e' la stessa scelta di `indirizzo.ps1` e di `avvia.sh` per la voce.
#
#   modello.ps1             controllo all'avvio (poche righe, per avvia.bat)
#   modello.ps1 -Dettaglio  diagnosi completa, con cosa fare (verifica-modello.bat)

param(
    [string]$Python = "",
    [switch]$Dettaglio
)

$ErrorActionPreference = "Continue"

# L'app sta nella cartella sopra `windows\`.
$App = Split-Path $PSScriptRoot -Parent

# --- l'interprete dell'app ---
# avvia.bat lo passa gia' pronto (`-Python`); da solo si cerca la venv accanto
# al progetto, e in ultima istanza il python del PATH.
if (-not $Python) {
    $candidato = Join-Path $App ".venv-win\Scripts\python.exe"
    if (Test-Path $candidato) { $Python = $candidato } else { $Python = "python" }
}

function Scrivi($testo) { Write-Host $testo }

# --- cosa usa l'app, chiesto all'app ---
# `base_url`, `modello`, se e' un endpoint locale (Ollama) e se e' configurato.
# La chiave non si legge: qui non serve e non va mostrata.
$Base = ""
$Modello = ""
$Locale = $false
$Configurato = $false
$Letto = $false
try {
    $py = @'
import comprensione as c
print(c.base_url())
print(c.modello())
print("1" if c._e_locale() else "0")
print("1" if c.configurato() else "0")
'@
    # `avvia.bat` entra in `windows\` prima di chiamare questo file, quindi il
    # processo python erediterebbe quella cartella: da li' `import comprensione`
    # fallisce (i moduli stanno nella cartella sopra) e lo stato del modello
    # sembrava illeggibile proprio quando tutto era a posto. Si esegue dalla
    # cartella dell'app, dove i moduli si trovano.
    Push-Location $App
    try {
        $righe = & $Python -c $py 2>$null
        $codice = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($codice -eq 0 -and $righe.Count -ge 4) {
        $Base = "$($righe[0])".Trim()
        $Modello = "$($righe[1])".Trim()
        $Locale = "$($righe[2])".Trim() -eq "1"
        $Configurato = "$($righe[3])".Trim() -eq "1"
        $Letto = $true
    }
} catch { }

function Riga-Modello {
    if (-not $Letto) {
        Scrivi "  Modello: non riesco a leggere la configurazione dell'app."
        Scrivi "           Avvia l'app una volta con avvia.bat e riprova."
        return 2
    }
    if (-not $Configurato) {
        # Nessuna chiave e nessun endpoint locale: l'app usa le regole. Non e' un
        # guasto, e' la configurazione di partenza.
        Scrivi "  Modello: non configurato, l'app usa le regole."
        return 2
    }
    if (-not $Locale) {
        # Servizio in rete compatibile OpenAI: non e' Ollama, quindi non c'e' un
        # elenco dei modelli da controllare. Si dice solo che e' configurato: la
        # comprensione col modello e' attiva, quindi se non capisce e' il
        # servizio a non rispondere o a rispondere male, non una preferenza.
        Scrivi "  Modello: servizio in rete configurato ($Modello)."
        Scrivi "           La comprensione col modello e' attiva: se non capisce,"
        Scrivi "           controlla che il servizio risponda su $Base."
        return 0
    }

    # Endpoint locale: e' Ollama. L'elenco dei modelli sta in /api/tags, non in
    # /v1 (che e' la parte compatibile OpenAI).
    $tags = ""
    try {
        $u = [Uri]$Base
        $tags = "$($u.Scheme)://$($u.Authority)/api/tags"
    } catch { }

    $nomi = @()
    $risponde = $false
    if ($tags) {
        try {
            $dati = Invoke-RestMethod -Uri $tags -TimeoutSec 5 -Method Get
            $risponde = $true
            $nomi = @($dati.models | ForEach-Object { "$($_.name)" })
        } catch { }
    }

    if (-not $risponde) {
        Scrivi "  Modello: Ollama NON risponde su $Base."
        Scrivi "           L'app usa le regole. Apri Ollama (deve stare nella tray)"
        Scrivi "           e riprova; non c'e' niente da reinstallare."
        return 1
    }

    # Il nome puo' avere il tag del modello (es. ':latest'): si confronta anche
    # senza tag, cosi' non si dice "manca" per una differenza di scrittura.
    $trovato = $nomi | Where-Object { $_ -eq $Modello -or ($_ -split ':')[0] -eq $Modello }
    if (-not $trovato) {
        Scrivi "  Modello: Ollama risponde, ma '$Modello' non e' scaricato."
        Scrivi "           Scaricalo con:  ollama pull $Modello"
        return 1
    }

    # Ollama pronto **e** modello presente: la comprensione col modello e' attiva
    # (non c'e' piu' un interruttore da accendere).
    Scrivi "  Modello: Ollama pronto, '$Modello' c'e'."
    Scrivi "           La comprensione col modello e' attiva."
    return 0
}

if ($Dettaglio) {
    Scrivi ""
    Scrivi "  ============================================"
    Scrivi "   Verifica: il modello di casa (Ollama)"
    Scrivi "  ============================================"
    Scrivi ""
    $esito = Riga-Modello
    Scrivi ""
    if ($esito -eq 0) {
        Scrivi "   Il modello e' pronto e attivo. Se l'app non capisce una frase,"
        Scrivi "   il modello non l'ha compresa: il parser a regole resta la rete"
        Scrivi "   di sicurezza, quindi la frase viene comunque interpretata."
    } elseif ($esito -eq 2) {
        Scrivi "   Nessun modello: l'app funziona lo stesso, con le regole."
        Scrivi "   Per accenderlo, vedi 'Il modello in casa, con Ollama' in LEGGIMI.md."
    } else {
        Scrivi "   Manca qualcosa: il punto qui sopra dice cosa fare."
    }
    Scrivi "  ============================================"
    Scrivi ""
    Read-Host "  Premi Invio per chiudere"
} else {
    # All'avvio: poche righe, senza fermare la finestra.
    Riga-Modello | Out-Null
}

exit 0
