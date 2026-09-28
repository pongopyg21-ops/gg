"""Ripara l'area della voce, senza toccare la chiave.

Perche' esiste, quando c'e' gia' `voce.bat`: quello rifa' tutto da capo e
richiede anche la chiave, che invece e' probabilmente giusta. Qui si corregge
**solo** l'area, e solo se non e' una di quelle Azure.

Il caso che lo ha reso necessario: in `segreto.bat` era finita l'area `s` (la "S"
della conferma scritta al prompt sbagliato), e l'app rispondeva con un errore di
risoluzione del nome che sembrava internet rotto. E, poiche' su Windows i file
dei segreti sono **due**, correggere `segreto.txt` non serviva a niente: comanda
`windows\\segreto.bat`, che `avvia.bat` chiama prima di partire e che imposta
l'ambiente.

Perche' in Python e non in un `.bat`: la modifica tocca una riga di un file che
contiene la chiave, e una riga scritta male la rovinerebbe. Qui si legge, si
sostituisce **solo** la riga dell'area e si riscrive; la chiave non viene mai
toccata ne' mostrata. Inoltre si prova davvero, come tutto il resto.

    python ripara_voce.py            # chiede l'area se serve
    python ripara_voce.py --area italynorth   # senza domande
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import voce_cloud

# Dove puo' stare l'area, in ordine di precedenza. `windows/segreto.bat` viene
# per primo perche' e' quello che **comanda** su Windows: `avvia.bat` lo chiama e
# il suo `set` finisce nell'ambiente, da cui l'app legge prima di ogni file.
def _file_candidati(base: str) -> list[str]:
    windows = os.path.join(base, "windows")
    return [
        os.path.join(windows, "segreto.bat"),
        os.path.join(base, "segreto.txt"),
        os.path.join(base, "segreto"),
        os.path.join(base, "segreto.sh"),
        os.path.join(base, "segreto.bat"),
    ]


def _leggi_area(percorso: str) -> str:
    """L'area scritta in questo file, o stringa vuota.

    Si accettano le due forme che l'app legge: `AZURE_SPEECH_REGION=...` (la
    forma dei file a script) e `area: ...` (la forma a etichette, piu' facile da
    scrivere a mano). Senza la seconda, un file scritto a mano non verrebbe
    riconosciuto e il riparatore aggiungerebbe una riga **dopo** quella vecchia:
    la vecchia resterebbe e, siccome il primo valore letto vince, l'area
    sbagliata continuerebbe a comandare."""
    try:
        testo = open(percorso, encoding="utf-8-sig", errors="replace").read()
    except OSError:
        return ""
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga or riga.startswith(("#", "REM ", "rem ", "@")):
            continue
        m = re.match(r"(?:set\s+\"?)?(AZURE_SPEECH_REGION|area|regione)\s*[:=]\s*[\"']?(.*)$",
                     riga, re.I)
        if m:
            return m.group(2).strip().strip("\"'").strip()
    return ""


def _scrivi_area(percorso: str, area: str) -> None:
    """Sostituisce **solo** la riga dell'area. La chiave non si tocca.

    Si riconosce sia `AZURE_SPEECH_REGION=...` sia `area: ...`: la riga nuova si
    scrive nella **stessa forma** di quella trovata, cosi' il file resta coerente
    con com'era. Se la riga non c'e', si aggiunge in fondo nel formato dei file a
    script, che l'app legge sempre."""
    with open(percorso, encoding="utf-8-sig", errors="replace") as fh:
        righe = fh.read().splitlines()

    trovata = False
    for i, riga in enumerate(righe):
        if riga.strip().startswith(("REM", "rem", "@")):
            continue
        m = re.match(r"(?:set\s+\"?)?(AZURE_SPEECH_REGION|area|regione)\s*[:=]", riga, re.I)
        if not m:
            continue
        etichetta = m.group(1)
        # stessa forma di prima: se era `area: ...` resta un'etichetta italiana
        if etichetta.lower() in ("area", "regione"):
            righe[i] = f"area: {area}"
        else:
            righe[i] = f'set "AZURE_SPEECH_REGION={area}"'
        trovata = True
    if not trovata:
        righe.append(f'set "AZURE_SPEECH_REGION={area}"')

    with open(percorso, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(righe) + "\n")


def _chiedi_area(attuale: str) -> str:
    print(f"\n  L'area scritta adesso e': «{attuale}»" if attuale else
          "\n  Non c'e' nessuna area nel file.")
    print("\n  Serve l'area della tua risorsa Speech, quella che si copia da")
    print("  portal.azure.com (la riga si chiama «Localita'/Area»).")
    print("  Esempi: italynorth, westeurope, eastus, uksouth")
    print("  Tutta minuscola, una parola sola, senza spazi.\n")
    while True:
        risposta = input("  Scrivi l'area [invio per italynorth]: ").strip()
        area = (risposta or "italynorth").strip("'\"").replace(" ", "").lower()
        if voce_cloud.area_valida(area):
            return area
        print(f'\n  «{area}» non e\' un\'area Azure. Riprovo.\n')


def ripara(base: str, area: str | None = None, chiedi=_chiedi_area) -> int:
    """Corregge l'area nel file che comanda. 0 se e' a posto, 1 se non si puo'.

    `area` assente significa "chiedila": cosi' la stessa funzione si usa dal
    comando e dai test."""
    candidati = [p for p in _file_candidati(base) if os.path.exists(p)]
    if not candidati:
        print("  Non trovo nessun file con la chiave della voce.")
        print("  Rilancia `voce.bat`: quello lo crea da zero.")
        return 1

    # il primo che **contiene** un'area e' quello che comanda; se nessuno la
    # contiene, si usa il primo esistente (probabilmente ha solo la chiave)
    percorso = next((p for p in candidati if _leggi_area(p)), candidati[0])
    attuale = _leggi_area(percorso)

    print(f"  File da correggere: {percorso}")
    if voce_cloud.area_valida(attuale):
        print(f"\n  L'area «{attuale}» e' valida: non c'e' niente da correggere.")
        print("\n  Se la voce non funziona lo stesso, il problema e' un altro:")
        print("  controlla la chiave, o rilancia `voce.bat`.")
        return 0

    nuova = area or chiedi(attuale)
    if not voce_cloud.area_valida(nuova):
        print(f'\n  «{nuova}» non e\' un\'area Azure: non tocco niente.')
        return 1

    _scrivi_area(percorso, nuova)
    print(f"\n  Fatto: area corretta in «{nuova}», nella riga di:\n     {percorso}")
    print("  La chiave e' rimasta quella che c'era.")
    print("\n  Ora riapri l'app: all'avvio deve comparire")
    print(f"     Voce neurale Azure attiva (area: {nuova})")
    return 0


def main() -> int:
    area = None
    if "--area" in sys.argv:
        area = sys.argv[sys.argv.index("--area") + 1].strip().lower()
    base = os.path.dirname(os.path.abspath(__file__))
    print()
    print("  ==========================================================")
    print("   Ripara la voce - Il Maggiordomo")
    print("  ==========================================================")
    return ripara(base, area)


if __name__ == "__main__":
    sys.exit(main())
