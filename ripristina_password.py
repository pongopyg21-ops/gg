"""Strumento per ripristinare l'accesso quando la password di una casa e' persa.

La password non si puo' recuperare: nel registro c'e' solo l'impronta, non la
password. Si puo' pero' metterne una nuova, e questo programma lo fa senza
chiedere quella vecchia. Serve ad avere di nuovo i propri dati, non a entrare
in casa d'altri: chi ha i file ha gia' i dati.

Non fa parte dell'app e non si usa dal browser: e' un comando, da eseguire sul
computer dove l'app vive. Vedi `windows/password.bat`.
"""

from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import houses  # noqa: E402


def _dimensione(path: str) -> str:
    if not os.path.exists(path):
        return "non trovato"
    byte = os.path.getsize(path)
    return f"{byte / 1024:.0f} KB" if byte >= 1024 else f"{byte} byte"


def _conta(db_path: str) -> tuple[int | None, str]:
    """Quante ricette in un database, e lo stato in una parola."""
    if not os.path.exists(db_path):
        return None, "file mancante"
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
            n = db.execute("SELECT count(*) FROM recipes").fetchone()[0]
    except sqlite3.Error:
        return None, "illeggibile"
    return n, f"{n} ricette"


def _database_candidati() -> list[str]:
    """I database di dati che esistono accanto all'app.

    Si guardano sia quello storico (`cucina.db`) sia quelli delle case
    (`case\\case-*.db`): se i dati non sono dove la casa punta, e' qui che si
    vedono, e senza questo elenco si cambierebbe la password della casa sbagliata.
    """
    trovi = []
    for cartella in (houses.DATA_DIR, houses.CASE_DIR):
        if not os.path.isdir(cartella):
            continue
        for nome in sorted(os.listdir(cartella)):
            if nome.endswith(".db"):
                trovi.append(os.path.join(cartella, nome))
    return trovi


def chiedi_nascosta(prompt: str) -> str:
    """Legge la password stampando un asterisco per carattere.

    `getpass` non mostra niente mentre si digita: non si vede nemmeno che i tasti
    arrivano, e si crede che la tastiera sia bloccata. Qui si da' un segno visibile
    per ogni carattere, senza rivelare quali siano.
    """
    print(f"  {prompt}", end="", flush=True)

    if os.name != "nt":
        import getpass
        try:
            return getpass.getpass("")
        except Exception:
            return input()

    import msvcrt
    caratteri: list[str] = []
    while True:
        c = msvcrt.getwch()
        if c in ("\r", "\n"):
            print()
            return "".join(caratteri)
        if c == "\003":                      # Ctrl-C
            raise KeyboardInterrupt
        if c == "\b":                        # backspace: si corregge, come ci si aspetta
            if caratteri:
                caratteri.pop()
                print("\b \b", end="", flush=True)
            continue
        if c in ("\x00", "\xe0"):            # tasto speciale: ha un secondo byte
            msvcrt.getwch()
            continue
        caratteri.append(c)
        print("*", end="", flush=True)


def _backup_registro() -> str:
    """Copia il registro prima di toccarlo.

    Cambiare una password e' reversibile (si rifa'), ma il file no: averne una
    copia accanto costa niente e toglie di mezzo il caso irreparabile.
    """
    import shutil
    destinazione = houses.REGISTRY_PATH + ".prima-del-cambio"
    shutil.copy2(houses.REGISTRY_PATH, destinazione)
    return destinazione


def _scegli(case: list[dict]) -> dict | None:
    if len(case) == 1:
        return case[0]
    nome = input("  Di quale casa vuoi rifare la password? ").strip()
    return next((c for c in case if c["nome"].lower() == nome.lower()
                 or c["slug"] == nome.lower()), None)


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
        _, stato = _conta(db)
        print(f"    {c['nome']}  ({c['slug']})")
        print(f"      dati: {db}")
        print(f"      peso: {_dimensione(db)} - {stato}")
    print()

    candidati = _database_candidati()
    if len(candidati) > 1:
        print("  Database di dati trovati accanto all'app:")
        for path in candidati:
            _, stato = _conta(path)
            print(f"    {stato:14} {_dimensione(path):>8}  {path}")
        print()

    scelta = _scegli(case)
    if scelta is None:
        print("  Non trovo nessuna casa con quel nome.")
        return 1

    db_scelta = houses.db_path(scelta["slug"])
    ricette, _ = _conta(db_scelta)
    print()
    print(f"  Casa scelta: {scelta['nome']}")

    # Un avviso, non un divieto: la password va rifatta anche se i dati non sono
    # qui, ma se le ricette sono altrove conviene fermarsi e guardare l'elenco.
    if ricette == 0:
        altrove = [p for p in candidati if p != db_scelta and (_conta(p)[0] or 0) > 0]
        print("  Nota: in questo database non risultano ricette.")
        if altrove:
            print("  Le tue ricette risultano invece in:")
            for path in altrove:
                print(f"    {_conta(path)[1]:14} {path}")

    print("  La password attuale non serve: nel registro c'e' solo l'impronta,")
    print("  e un'impronta non si riporta indietro.")
    print()

    nuova = chiedi_nascosta("Password nuova: ")
    if not nuova or len(nuova) < 4:
        print("  Serve almeno 4 caratteri. Non ho cambiato niente.")
        return 1
    conferma = chiedi_nascosta("Ripetila per sicurezza: ")
    if nuova != conferma:
        print("  Le due non coincidono. Non ho cambiato niente.")
        return 1

    try:
        copia = _backup_registro()
        houses.reimposta_password(scelta["slug"], nuova)
    except (ValueError, OSError) as err:
        print(f"  {err}")
        return 1

    # la prova che l'accesso e' tornato: se la verifica fallisse, la password
    # appena scritta non vale e va detto ora, non al prossimo tentativo di entrare
    if not houses.autentica(scelta["slug"], nuova):
        print("  Qualcosa non ha funzionato: la password nuova non risulta valida.")
        print(f"  Il registro di prima e' qui, intatto: {copia}")
        return 1

    print()
    print(f"  Fatto. Entra come \"{scelta['nome']}\" con la password nuova.")
    print("  I dati non sono stati toccati: ricette, dispensa e magazzino sono sempre li'.")
    print(f"  Se qualcosa non tornasse, il registro di prima e' qui: {copia}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
