"""Informazioni utili: Wi-Fi, indirizzi, contatti, codici.

Non e' un manuale di istruzioni ma un posto dove tenere le cose che si cercano
sempre e non si ricordano mai: la password del Wi-Fi di casa, l'indirizzo
dell'ambulatorio, il numero dell'idraulico, il codice del cancello.

Le voci sono un dato, non una costante: stanno nella tabella `faq` e si
gestiscono dall'interfaccia. Qui vivono solo le categorie, che sono la struttura
della sezione e non un contenuto dell'utente — come gli ambienti per le pulizie.

Due scelte deliberate:

- il testo della voce sta in `answer` e puo' essere lungo (un indirizzo con
  citofono e piano, gli orari di un ambulatorio): nel form e' un'area di testo,
  non una riga sola, perche' costringere a stare su una riga spinge a tagliare
  proprio le informazioni che servono.
- `secret` non e' una protezione: il valore viaggia comunque nella risposta
  dell'API, e chi apre gli strumenti del browser lo vede. Serve a non tenere una
  password scritta sullo schermo quando qualcuno passa dietro la scrivania o si
  fa uno screenshot. Trattarlo come se fosse sicurezza sarebbe peggio che non
  averlo, perche' farebbe abbassare la guardia.
"""

# ------------------------------------------------------------------ categorie
# L'ordine di questa lista e' l'ordine in cui le voci vengono mostrate: prima le
# cose che si cercano piu' spesso, poi il resto.

CATEGORIE = [
    {"key": "wifi", "label": "Wi-Fi"},
    {"key": "indirizzi", "label": "Indirizzi"},
    {"key": "contatti", "label": "Contatti"},
    {"key": "codici", "label": "Codici e accessi"},
    {"key": "generale", "label": "Generale"},
]

CATEGORIA_DEFAULT = "generale"

_CHIAVI = [c["key"] for c in CATEGORIE]
_ORDINE = {k: i for i, k in enumerate(_CHIAVI)}


def categorie():
    return [dict(c) for c in CATEGORIE]


def categoria_valida(key):
    """La chiave se e' una categoria nota, altrimenti quella predefinita.

    Una categoria sconosciuta non e' un errore da bloccare: puo' arrivare da un
    database scritto a mano o da una versione precedente, e una voce e' troppo
    utile per rifiutarla per un'etichetta sbagliata.
    """
    return key if key in _ORDINE else CATEGORIA_DEFAULT


def etichetta(key):
    for c in CATEGORIE:
        if c["key"] == key:
            return c["label"]
    return CATEGORIE[-1]["label"]


def ordina(voci):
    """Per categoria, poi in evidenza, poi per titolo.

    L'ordine e' fisso e non dipende da quando la voce e' stata aggiunta: una
    lista di consultazione si scorre con gli occhi, e se cambia ordine ogni volta
    non si impara mai dove sono le cose. Le voci in evidenza risalgono in cima
    **alla propria categoria**, non all'elenco: raggruppate per categoria, farle
    saltare fuori dal gruppo le staccherebbe dalle voci affini.
    """
    return sorted(voci, key=lambda v: (
        _ORDINE.get(v.get("category"), len(_ORDINE)),
        not v.get("pinned"),
        (v.get("question") or "").lower(),
    ))
