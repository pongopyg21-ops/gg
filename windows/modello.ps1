# Dice se il modello di casa (Ollama) e' pronto: se risponde, se il modello che
# l'app si aspetta e' stato scaricato, e cosa fare se no.
#
# Il guasto che questo file rende visibile: Ollama installato e il modello
# scaricato, ma l'app continua a usare le regole perche' l'interruttore in
# **Profilo > Capire i comandi** e' spento — e nessuno lo dice. Le tre cause
# (Ollama spento, modello diverso, interruttore spento) si confondono fra loro e
# danno lo stesso sintomo: "il modello non capisce".
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
    $righe = & $Python -c $py 2>$null
    if ($LASTEXITCODE -eq 0 -and $righe.Count -ge 4) {
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
        # elenco dei modelli da controllare. Si dice solo che e' configurato.
        Scrivi "  Modello: servizio in rete configurato ($Modello)."
        Scrivi "           Se non capisce, controlla l'interruttore in Profilo > Capire i comandi."
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

    # Ollama pronto **e** modello presente: resta l'interruttore, che e' spento
    # di partenza ed e' la causa piu' frequente del "non capisce".
    Scrivi "  Modello: Ollama pronto, '$Modello' c'e'."
    Scrivi "           Per usarlo: Profilo > Capire i comandi > accendi l'interruttore."
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
        Scrivi "   Il modello e' pronto. Se l'app non capisce le frasi, l'unica"
        Scrivi "   cosa che resta e' l'interruttore: Profilo > Capire i comandi."
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
