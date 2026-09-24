"""Copie automatiche dei dati, per non dipendere dalla memoria dell'utente.

Il pulsante "Scarica una copia dei dati" esiste, ma serve solo a chi si ricorda
di premerlo: la copia che salva davvero e' quella che non si deve chiedere. Il
database raccoglie mesi di lavoro e dati che non si ricostruiscono da nessuna
parte (la password del Wi-Fi, i codici), quindi una copia dimenticata e' una
copia che non c'e' nel momento in cui serve.

Si copia con l'API di backup di SQLite e non copiando il file: una copia fatta
mentre il server sta scrivendo prende il database a meta' e da' un file corrotto,
cioe' peggio di nessuna copia. L'API di backup sa prendere un'istantanea
coerente anche con scritture in corso.

Si tiene **una copia al giorno** e si conservano le ultime `QUANTE`. Una copia
d'ora in ora sarebbe piu' fitta ma non piu' utile — l'errore che ci si accorge
di aver fatto e' quasi sempre di ieri o di qualche giorno prima — e riempirebbe
il disco. Le copie piu' vecchie si tolgono, cosi' la cartella non cresce senza
limite su una macchina lasciata accesa per mesi.
"""

import datetime
import os
import shutil
import sqlite3
import time
from contextlib import closing

import houses


def cartella():
    """Dove stanno le copie: accanto ai dati, cosi' una sola cartella da salvare.

    Si calcola a ogni chiamata e non una volta all'importazione: `houses.DATA_DIR`
    cambia fra l'ambiente di prova e quello vero, e una costante fissata troppo
    presto scriverebbe le copie nel posto sbagliato."""
    return os.path.join(houses.DATA_DIR, "copie")

# Ogni quanto fare una copia e quante conservarne. Il giorno non si conta a
# mezzanotte ma a distanza dall'ultima copia: cosi' un server acceso solo di
# pomeriggio non salta mai la copia, e uno riavviato non ne fa due di seguito.
ORE_TRA_COPIE = 24
QUANTE = 7

PREFISSO = "dati-"


def _percorso_copia(slug, quando=None):
    """Dove finisce la copia di una casa: `<cartella>/<slug>/dati-AAAAMMGG-HHMMSS.db`."""
    quando = quando or datetime.datetime.now()
    return os.path.join(cartella(), slug, f"{PREFISSO}{quando.strftime('%Y%m%d-%H%M%S')}.db")


def _copie_di(slug):
    """Le copie di una casa, dalla piu' recente alla piu' vecchia."""
    dove = os.path.join(cartella(), slug)
    if not os.path.isdir(dove):
        return []
    file = [os.path.join(dove, f) for f in os.listdir(dove)
            if f.startswith(PREFISSO) and f.endswith(".db")]
    # il nome porta la data, quindi l'ordine alfabetico e' anche quello
    # cronologico: piu' affidabile della data di modifica, che un copia-incolla
    # o un ripristino di un backup del disco possono cambiare
    return sorted(file, reverse=True)


def elenco(slug):
    """Le copie di una casa come le legge l'interfaccia: quante e quando l'ultima."""
    file = _copie_di(slug)
    ultima = file[0] if file else None
    return {
        "quante": len(file),
        "conservate": QUANTE,
        "ultima": (datetime.datetime.fromtimestamp(os.path.getmtime(ultima))
                   .strftime("%Y-%m-%d %H:%M") if ultima else None),
    }


def _ultima(slug):
    copie = _copie_di(slug)
    return copie[0] if copie else None


def _e_ora(slug, adesso=None):
    """True se per questa casa l'ultima copia e' abbastanza vecchia.

    La copia appena fatta vale anche se il file non e' leggibile: rifarla non la
    riparerebbe, e un errore di lettura ripetuto a ogni giro riempirebbe il log.
    """
    ultima = _ultima(slug)
    if not ultima:
        return True
    adesso = adesso or time.time()
    return (adesso - os.path.getmtime(ultima)) >= ORE_TRA_COPIE * 3600


def _ruota(slug):
    """Toglie le copie oltre `QUANTE`, dalla piu' vecchia in poi."""
    for vecchia in _copie_di(slug)[QUANTE:]:
        try:
            os.remove(vecchia)
        except OSError:
            # una copia che non si riesce a togliere non deve fermare le altre:
            # si riprovera' al giro dopo, e intanto non si perde niente
            pass


def copia_casa(slug, quando=None):
    """Fa la copia di una casa. Ritorna il percorso, o None se non c'e' niente da copiare.

    Scrittura atomica: la copia si prepara con un nome provvisorio e si rinomina
    solo a lavoro finito. Un file a meta' che porta il nome di una copia buona e'
    la trappola peggiore, perche' la si crede valida fino al giorno in cui serve.
    """
    origine = houses.db_path(slug)
    if not os.path.exists(origine):
        return None

    destinazione = _percorso_copia(slug, quando)
    os.makedirs(os.path.dirname(destinazione), exist_ok=True)
    provvisorio = destinazione + ".tmp"

    try:
        with closing(sqlite3.connect(origine)) as da, closing(sqlite3.connect(provvisorio)) as a:
            da.backup(a)
    except sqlite3.Error:
        # se la copia non riesce si toglie il provvisorio: un file non finito
        # nella cartella verrebbe contato come copia valida al giro dopo
        try:
            os.remove(provvisorio)
        except OSError:
            pass
        raise
    os.replace(provvisorio, destinazione)
    _ruota(slug)
    return destinazione


def fai_copie(adesso=None, forse=False):
    """Fa la copia delle case che ne hanno bisogno. Ritorna l'elenco dei file scritti.

    `forse=True` copia solo le case la cui ultima copia e' vecchia; e' il modo in
    cui gira da sola. Con `forse=False` copia sempre, che e' quello che serve al
    pulsante e ai test.
    """
    scritte = []
    for casa in houses.elenco():
        slug = casa["slug"]
        if forse and not _e_ora(slug, adesso):
            continue
        percorso = copia_casa(slug)
        if percorso:
            scritte.append(percorso)
    return scritte


def svuota():
    """Toglie tutte le copie. Usata dai test per partire da zero."""
    if os.path.isdir(cartella()):
        shutil.rmtree(cartella(), ignore_errors=True)
