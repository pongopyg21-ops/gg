"""Calendario degli impegni: le date che contano, con un promemoria.

Appuntamenti, scadenze, ricorrenze. Sta dentro Progetti perche' e' una cosa da
fare, come i progetti e il magazzino: non entra in nessuna ricetta e non si
scala dal fabbisogno della spesa.

Perche' e' una tabella a parte e non una colonna dei progetti: un progetto ha
un periodo (inizio e fine) e una priorita', un impegno ha un **giorno preciso**
e un'ora. Sono due forme diverse — un progetto puo' durare un mese, un impegno
no — e tenerli nella stessa tabella costringerebbe meta' delle righe ad avere
campi vuoti che non significano niente.

Due scelte deliberate:

- **Il promemoria e' quanti giorni prima**, non una data di avviso: cosi'
  spostare l'impegno sposta anche il promemoria, invece di lasciarlo indietro.
  Una data di avviso salvata a parte si disallinea al primo rinvio, ed e' il
  caso in cui il promemoria smette di servire.
- **Il colore e' una categoria, non una decorazione**: lavoro, casa, salute,
  famiglia, altro. Serve a leggere il mese a colpo d'occhio, non a fare bello.
  E' testo libero con suggerimenti (catalogo qui sotto), non un vincolo: la
  vita di ognuno ha categorie che non si prevedono, e rifiutare un impegno
  perche' l'etichetta non e' in elenco sarebbe un ostacolo senza vantaggio.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

# --------------------------------------------------------------- categorie
# L'ordine e' quello di visualizzazione. `colore` e' un nome di variabile CSS
# (definita in style.css), non un codice esadecimale: cosi' il tema scuro la
# schiarisce da sola, e cambiare palette non vuol dire toccare questo file.

CATEGORIE = [
    {"key": "lavoro", "label": "Lavoro", "colore": "--cat-lavoro"},
    {"key": "casa", "label": "Casa", "colore": "--cat-casa"},
    {"key": "salute", "label": "Salute", "colore": "--cat-salute"},
    {"key": "famiglia", "label": "Famiglia", "colore": "--cat-famiglia"},
    {"key": "altro", "label": "Altro", "colore": "--cat-altro"},
]
CATEGORIA_DEFAULT = "altro"

# Le anticipazioni del promemoria che si possono scegliere. Lo zero e' "il
# giorno stesso": e' una scelta legittima, non un "nessun promemoria".
PROMEMORIA = [
    {"giorni": 0, "label": "Il giorno stesso"},
    {"giorni": 1, "label": "1 giorno prima"},
    {"giorni": 2, "label": "2 giorni prima"},
    {"giorni": 3, "label": "3 giorni prima"},
    {"giorni": 7, "label": "1 settimana prima"},
    {"giorni": 14, "label": "2 settimane prima"},
    {"giorni": 30, "label": "1 mese prima"},
]
PROMEMORIA_MAX = 365

# Quante volte al giorno si guarda il calendario: oltre, un impegno e' rumore.
# Ma il conteggio e' della casa, quindi ognuno ha il suo.
GIORNI_AVVISO = 30


def categoria_valida(chiave):
    """La chiave di categoria, o quella predefinita se sconosciuta.

    Si fa ricadere invece di rifiutare: un'etichetta sbagliata non deve far
    perdere un appuntamento. E' la stessa scelta fatta per le FAQ.
    """
    chiave = (chiave or "").strip().lower()
    for c in CATEGORIE:
        if c["key"] == chiave:
            return chiave
    return CATEGORIA_DEFAULT


def categoria(chiave):
    """La voce di catalogo di una categoria (mai None)."""
    chiave = categoria_valida(chiave)
    return next(c for c in CATEGORIE if c["key"] == chiave)


def _data(valore):
    """Una data ISO, o None se assente/illeggibile."""
    if not valore:
        return None
    try:
        return date.fromisoformat(str(valore)[:10])
    except ValueError:
        return None


def _ora(valore):
    """Un'ora HH:MM valida, o stringa vuota. Tollerante: un'ora scritta male
    non deve far perdere l'impegno, che e' la parte che conta."""
    testo = (valore or "").strip()
    if not testo:
        return ""
    try:
        datetime.strptime(testo[:5], "%H:%M")
    except ValueError:
        return ""
    return testo[:5]


def promemoria_giorni(valore):
    """Quanti giorni prima avvisare, entro i limiti. Zero e' il giorno stesso."""
    try:
        n = int(valore)
    except (TypeError, ValueError):
        return 0
    return max(0, min(PROMEMORIA_MAX, n))


def stato_impegno(quando, oggi=None, promemoria=0):
    """Come si presenta un impegno rispetto a oggi.

    `giorni` e' la distanza dal giorno dell'impegno: **negativo se e' passato**,
    0 oggi, positivo se deve ancora venire. E' la stessa convenzione di
    `igiene.scadenza`, cosi' chi legge i due moduli non deve ricordarsi due
    regole diverse.

    `avvisa` e' vero quando il promemoria e' scattato: da `promemoria` giorni
    prima fino al giorno stesso. Dopo non avvisa piu', perche' un promemoria
    per una cosa gia' successa non e' un promemoria.
    """
    giorno = _data(quando)
    oggi_d = _data(oggi) or date.today()
    if giorno is None:
        return {"giorni": None, "passato": False, "oggi": False,
                "avvisa": False, "in_ritardo": False}
    giorni = (giorno - oggi_d).days
    passato = giorni < 0
    return {
        "giorni": giorni,
        "passato": passato,
        "oggi": giorni == 0,
        "avvisa": not passato and giorni <= promemoria,
        # "in ritardo" e' la cosa passata che non si e' ancora chiusa: e' quello
        # che si vuole vedere in cima, non tutto quello che e' passato
        "in_ritardo": passato,
    }


def quando_detto(stato):
    """La frase breve che descrive quando cade un impegno, per la scheda."""
    giorni = stato.get("giorni")
    if giorni is None:
        return "senza data"
    if giorni == 0:
        return "oggi"
    if giorni == 1:
        return "domani"
    if giorni == -1:
        return "ieri"
    if giorni > 1:
        return f"fra {giorni} giorni"
    return f"{abs(giorni)} giorni fa"


def mese_di(anno, mese):
    """Le celle del mese per la griglia: settimane intere, da lunedi' a domenica.

    La griglia si costruisce con i giorni **fuori dal mese** (le code del mese
    precedente e del successivo) perche' le settimane siano complete: una riga
    che comincia a meta' confonde piu' di quanto aiuti. `nel_mese` distingue
    quelli veri, cosi' le code si possono mostrare spente.
    """
    primo = date(anno, mese, 1)
    ultimo = date(anno + (mese == 12), (mese % 12) + 1, 1) - timedelta(days=1)
    inizio = primo - timedelta(days=primo.weekday())   # lunedi' della prima settimana
    fine = ultimo + timedelta(days=6 - ultimo.weekday())
    celle = []
    giorno = inizio
    while giorno <= fine:
        celle.append({
            "iso": giorno.isoformat(),
            "giorno": giorno.day,
            "nel_mese": giorno.month == mese and giorno.year == anno,
            "weekend": giorno.weekday() >= 5,
        })
        giorno += timedelta(days=1)
    return {
        "anno": anno,
        "mese": mese,
        "primo": primo.isoformat(),
        "ultimo": ultimo.isoformat(),
        "celle": celle,
    }


def mesi():
    """I dodici mesi in italiano, per le tendine e le intestazioni."""
    return [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
    ]


def meta():
    """Tutto quello che serve al client per disegnare il calendario."""
    return {
        "categories": [c["key"] for c in CATEGORIE],
        "category_labels": {c["key"]: c["label"] for c in CATEGORIE},
        "category_colors": {c["key"]: c["colore"] for c in CATEGORIE},
        "default_category": CATEGORIA_DEFAULT,
        "reminders": PROMEMORIA,
        "months": mesi(),
    }
