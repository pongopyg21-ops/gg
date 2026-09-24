"""Strumento per ripristinare l'accesso quando la password di una casa e' persa.

La password non si puo' recuperare: nel registro c'e' solo l'impronta, non la
password. Si puo' pero' metterne una nuova, e questo programma lo fa senza
chiedere quella vecchia. Serve ad avere di nuovo i propri dati, non a entrare
in casa d'altri: chi ha i file ha gia' i dati.

Non fa parte dell'app e non si usa dal browser: e' un comando, da eseguire sul
computer dove l'app vive. Vedi `windows/password.bat`.
"""

from __future__ import annotations

import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import houses  # noqa: E402


def _dimensione(path: str) -> str:
    if not os.path.exists(path):
        return "non trovato"
    byte = os.path.getsize(path)
    return f"{byte / 1024:.0f} KB" if byte >= 1024 else f"{byte} byte"


def _conta_ricette(path: str) -> int | None:
    """Quante ricette ci sono in un database. `None` se non e' leggibile."""
    import sqlite3
    if not os.path.exists(path):
        return None
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            return db.execute("SELECT count(*) FROM recipes").fetchone()[0]
    except sqlite3.Error:
        return None


def main() -> int:
    case = houses.elenco()
    if not case:
        print("  Non c'e' nessuna casa in questo computer.")
        print("  Se l'app non riconosce i tuoi dati, il registro non e' dove credi:")
        print("  controlla di essere nella cartella giusta, o la variabile")
        print("  MAGGIORDOMO_DATA se hai spostato i dati altrove.")
        return 1

    print()
    print(f"  Case presenti: {len(case)}")
    print()
    for c in case:
        db = houses.db_path(c["slug"])
        ricette = _conta_ricette(db)
        stato = f"{ricette} ricette" if ricette is not None else "vuota o non leggibile"
        print(f"    {c['nome']}  ({c['slug']})")
        print(f"      dati: {db}")
        print(f"      peso: {_dimensione(db)} - {stato}")
    print()

    if len(case) == 1:
        scelta = case[0]
    else:
        nome = (input("  Di quale casa vuoi rifare la password? ").strip())
        scelta = next((c for c in case if c["nome"].lower() == nome.lower()
                       or c["slug"] == nome.lower()), None)
        if scelta is None:
            print(f"  Non trovo nessuna casa che si chiami \"{nome}\".")
            return 1

    print()
    print(f"  Casa scelta: {scelta['nome']}")
    print("  La password attuale non serve: nel registro c'e' solo l'impronta,")
    print("  e un'impronta non si riporta indietro.")
    print()

    nuova = getpass.getpass("  Password nuova: ")
    if not nuova or len(nuova) < 4:
        print("  Serve almeno 4 caratteri. Non ho cambiato niente.")
        return 1
    conferma = getpass.getpass("  Ripetila per sicurezza: ")
    if nuova != conferma:
        print("  Le due non coincidono. Non ho cambiato niente.")
        return 1

    try:
        houses.reimposta_password(scelta["slug"], nuova)
    except ValueError as err:
        print(f"  {err}")
        return 1

    # la prova che l'accesso e' tornato: se la verifica fallisse, la password
    # appena scritta non vale e va detto ora, non al prossimo tentativo di entrare
    if not houses.autentica(scelta["slug"], nuova):
        print("  Qualcosa non ha funzionato: la password nuova non risulta valida.")
        return 1

    print()
    print(f"  Fatto. Entra come \"{scelta['nome']}\" con la password nuova.")
    print("  I dati non sono stati toccati: ricette, dispensa e magazzino sono sempre li'.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
