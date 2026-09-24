# Attiva l'indirizzo pubblico stabile de Il Maggiordomo con Tailscale Funnel:
# un nome https://<computer>.<tuarete>.ts.net che non cambia piu', senza aprire
# porte sul router e senza toccarne le impostazioni.
#
# Perche' un file a parte e non una riga dentro dominio.bat: come per
# indirizzo.ps1, il linguaggio dei .bat tratta in modo speciale virgolette e
# caratteri di questi comandi, e un errore non si vedrebbe. Cosi' il codice sta
# dove si legge, e il .bat si limita a chiamarlo.

$ErrorActionPreference = "Continue"

# La porta a cui inoltrare il traffico: quella su cui ascolta l'app.
$Porta = if ($env:PORT) { $env:PORT } else { "12000" }

# tailscale.exe sta qui nell'installazione normale; se non c'e' (versione
# installata dallo Store, o percorso scelto a mano) si cerca nel PATH.
$Tailscale = "C:\Program Files\Tailscale\tailscale.exe"
if (-not (Test-Path $Tailscale)) {
    $cmd = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($cmd) { $Tailscale = $cmd.Source }
}
if (-not (Test-Path $Tailscale)) {
    Write-Host ""
    Write-Host "  Tailscale non risulta installato."
    Write-Host ""
    Write-Host "  1. Scaricalo da https://tailscale.com/download/windows"
    Write-Host "  2. Installalo e accedi con un account (Google, Microsoft o GitHub)"
    Write-Host "  3. Riapri questo file"
    Write-Host ""
    Write-Host "  E' gratuito: bastano gli account personali, non serve pagare."
    exit 1
}

# Se non e' collegato, funnel non puo' fare nulla: meglio dirlo adesso che
# lasciare un errore incomprensibile.
& $Tailscale status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  Tailscale e' installato ma non collegato."
    Write-Host "  Apri Tailscale dal menu Start e accedi, poi riprova."
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "  Attivo l'indirizzo pubblico sulla porta $Porta..."
Write-Host "  La prima volta Tailscale apre il browser per l'approvazione:"
Write-Host "  va concessa una volta sola."
Write-Host ""

# `--bg` e' quello che rende l'indirizzo permanente: senza, al riavvio del
# computer andrebbe riattivato a mano ogni volta.
& $Tailscale funnel --bg $Porta
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  Non sono riuscito ad attivare l'indirizzo."
    Write-Host "  Il messaggio qui sopra dice cosa manca; quasi sempre e'"
    Write-Host "  l'approvazione nel browser, da completare una volta."
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "  ============================================"
Write-Host "   Fatto. Il tuo indirizzo pubblico e':"
Write-Host "  ============================================"
Write-Host ""
& $Tailscale funnel status
Write-Host ""
Write-Host "  Quel nome https://...ts.net e' l'indirizzo da usare sempre:"
Write-Host "  dal telefono, da fuori casa, e per l'accesso con Google."
Write-Host "  Non cambia piu', anche riavviando il computer."
Write-Host ""
Write-Host "  Per spegnerlo:  tailscale funnel --bg $Porta off"
Write-Host ""
