# Stampa l'indirizzo del computer nella rete di casa: e' quello che si usa dal
# telefono. Vuoto se non lo trova.
#
# Perche' un file a parte e non una riga dentro avvia.bat: quel comando contiene
# virgolette e caratteri che il linguaggio dei file .bat tratta in modo speciale,
# e una sola virgoletta sbagliata lo fa fallire in silenzio. Cosi' invece il
# codice e' scritto dove si legge, e il .bat si limita a chiamarlo.

$indirizzo = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike '127.*' -and
        $_.IPAddress -notlike '169.254.*' -and   # indirizzo che Windows da' quando non c'e' rete
        $_.PrefixOrigin -ne 'WellKnown'
    } |
    Select-Object -First 1 -ExpandProperty IPAddress

# Silenzio se non c'e': il chiamante mostra la riga solo se ha qualcosa da dire.
if ($indirizzo) { Write-Output $indirizzo }
