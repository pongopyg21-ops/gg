"""Pulizie di casa: catalogo delle attivita' e quando vanno rifatte.

Il metodo viene dal calendario mensile delle pulizie (Momentocasa): le attivita'
si dividono in tre blocchi — quotidiane, settimanali, mensili — piu' un calendario
stagionale, un mese per l'altro, con un "focus" che dice l'intento del mese.

Il catalogo e' un dato, non una costante: viene seminato nella tabella `chores`
come le ricette, cosi' si puo' modificare, disattivare o aggiungere senza toccare
il codice.

Le scadenze non si salvano: si ricavano dall'ultima volta che un'attivita' e'
stata fatta. Una tabella di appoggio si disallineerebbe appena si registra un
completamento, come per i giorni della spesa.

Due scelte deliberate, perche' l'elenco e' la cosa che l'utente legge davvero:

- dove l'articolo ripete nel mese stagionale un lavoro gia' coperto da una voce
  mensile (i filtri degli elettrodomestici ad aprile, i materassi a febbraio, il
  bagno a fondo a luglio) la voce non viene duplicata: comparirebbe due volte
  nello stesso mese e la seconda sarebbe solo rumore.
- i consigli generici di dicembre ("pulizie leggere ma frequenti", "gestione
  strategica del disordine") non sono attivita' da spuntare: il loro senso sta
  nel focus del mese, che li raccoglie.
"""

from datetime import date, timedelta

# ------------------------------------------------------------------ costanti

# La cadenza in giorni di ogni blocco. "stagionale" non ha una cadenza vera:
# si fa una volta l'anno, nel mese indicato, e il conto lo fa `scadenza`.
CADENZE = {"giornaliera": 1, "settimanale": 7, "mensile": 30}

FREQUENZE = [
    {"key": "giornaliera", "label": "Ogni giorno", "giorni": 1},
    {"key": "settimanale", "label": "Ogni settimana", "giorni": 7},
    {"key": "mensile", "label": "Ogni mese", "giorni": 30},
    {"key": "stagionale", "label": "Una volta l'anno", "giorni": None},
]

AMBIENTI = ["Cucina", "Bagno", "Camere", "Soggiorno", "Ingresso",
            "Esterni", "Ripostigli", "Tutta la casa"]

GIORNI_SETTIMANA = ["lunedì", "martedì", "mercoledì", "giovedì",
                    "venerdì", "sabato", "domenica"]

# ---------------------------------------------------- blocchi per frequenza
# (nome, ambiente, minuti stimati). I minuti servono a far vedere quanto costa
# il piano di oggi prima di iniziare: e' il senso della regola dei 15 minuti.

QUOTIDIANE = [
    ("Riordino generale", "Tutta la casa", 5),
    ("Piatti e superfici della cucina", "Cucina", 10),
    ("Bagno fresco: lavandino e specchio", "Bagno", 5),
    ("Raccogliere gli oggetti fuori posto", "Tutta la casa", 5),
    ("Arieggiare le stanze", "Tutta la casa", 5),
]

SETTIMANALI = [
    ("Aspirare e lavare i pavimenti", "Tutta la casa", 30),
    ("Pulire il bagno in profondità", "Bagno", 25),
    ("Spolverare", "Tutta la casa", 15),
    ("Cambiare le lenzuola", "Camere", 10),
    ("Pulire la cucina a fondo", "Cucina", 20),
]

MENSILI = [
    ("Lavare vetri e specchi grandi", "Tutta la casa", 30),
    ("Pulire forno e frigorifero", "Cucina", 40),
    ("Igienizzare materassi e cuscini", "Camere", 30),
    ("Togliere la polvere alta: armadi, battiscopa, porte", "Tutta la casa", 25),
    ("Pulire i filtri degli elettrodomestici", "Cucina", 20),
    ("Riordinare armadi e cassetti a rotazione", "Camere", 40),
]

# ------------------------------------------------------- calendario annuale
# Il mese, il suo titolo e il focus dichiarato dall'articolo, con le attivita'
# che gli appartengono.

STAGIONALI = [
    {"mese": 1, "titolo": "Reset post-feste", "focus": "ripristinare ordine e spazio",
     "attivita": [
         ("Smaltire le decorazioni e riordinare le scatole", "Ripostigli", 30),
         ("Pulire frigorifero e freezer", "Cucina", 40),
         ("Lavare le tende del soggiorno", "Soggiorno", 30),
         ("Pulire divani e tessuti d'arredo", "Soggiorno", 45),
         ("Decluttering della cucina: spezie, dispensa, stoviglie", "Cucina", 40),
     ]},
    {"mese": 2, "titolo": "Cura delle superfici",
     "focus": "migliorare la qualità dell'aria e degli ambienti interni",
     "attivita": [
         ("Pulizia profonda dei pavimenti, battiscopa compresi", "Tutta la casa", 45),
         ("Lavare piumoni e coperte leggere", "Camere", 30),
         ("Pulire i termosifoni", "Tutta la casa", 25),
     ]},
    {"mese": 3, "titolo": "Preparazione alla primavera",
     "focus": "far entrare più luce possibile",
     "attivita": [
         ("Pulire vetri e infissi", "Tutta la casa", 45),
         ("Rinfrescare gli armadi e iniziare il cambio stagione", "Camere", 40),
         ("Lavare coperte, plaid e tappeti piccoli", "Camere", 30),
         ("Pulire balconi e davanzali", "Esterni", 30),
     ]},
    {"mese": 4, "titolo": "Grande pulizia primaverile",
     "focus": "alleggerire e rigenerare la casa",
     "attivita": [
         ("Pulire tapparelle o persiane", "Tutta la casa", 45),
         ("Lavare tende e copridivani", "Soggiorno", 40),
         ("Sgrassare la cucina a fondo", "Cucina", 45),
         ("Sistemare garage, cantina e ripostiglio", "Ripostigli", 50),
     ]},
    {"mese": 5, "titolo": "Outdoor e ordine globale",
     "focus": "prepararsi alla vita all'aria aperta",
     "attivita": [
         ("Sistemare balconi e terrazzi", "Esterni", 40),
         ("Lavare sedie e tavoli da esterno", "Esterni", 30),
         ("Pulire porte, maniglie e interruttori", "Tutta la casa", 25),
         ("Pulire lampadari e punti luce", "Tutta la casa", 30),
     ]},
    {"mese": 6, "titolo": "Cambio stagione e tessuti",
     "focus": "eliminare muffe, umidità e cattivi odori",
     "attivita": [
         ("Lavare e riporre maglioni, giacche pesanti e coperte", "Camere", 45),
         ("Organizzare gli armadi estivi", "Camere", 40),
         ("Pulire a fondo la lavatrice: cestello e guarnizioni", "Cucina", 30),
         ("Arieggiare e igienizzare le scarpiere", "Ingresso", 20),
     ]},
    {"mese": 7, "titolo": "Minimalismo e superfici",
     "focus": "mantenere la casa fresca e semplice",
     "attivita": [
         ("Decluttering dei cassetti", "Camere", 30),
         ("Pulire mobili e superfici grandi", "Tutta la casa", 35),
         ("Lavare i tappeti leggeri", "Soggiorno", 30),
     ]},
    {"mese": 8, "titolo": "Manutenzione elettrodomestici",
     "focus": "ridurre i consumi e aumentare l'efficienza",
     "attivita": [
         ("Pulire il condizionatore: filtri e griglie", "Tutta la casa", 30),
         ("Sbrinare gli eventuali freezer secondari", "Cucina", 40),
         ("Lavare cestelli, filtri e tubi della lavastoviglie", "Cucina", 30),
         ("Igienizzare la cucina con un ciclo di pulizia", "Cucina", 35),
     ]},
    {"mese": 9, "titolo": "Rientro alla routine",
     "focus": "ripartire con ordine mentale e fisico",
     "attivita": [
         ("Riordinare gli spazi di lavoro e la scrivania", "Soggiorno", 30),
         ("Pulire librerie e zone studio", "Soggiorno", 35),
         ("Organizzare dispensa e scorte", "Cucina", 40),
         ("Lavare le tende leggere", "Tutta la casa", 30),
     ]},
    {"mese": 10, "titolo": "Preparazione all'inverno",
     "focus": "creare un ambiente caldo e funzionale",
     "attivita": [
         ("Lavare plaid e coperte pesanti", "Camere", 35),
         ("Sistemare gli armadi invernali", "Camere", 40),
         ("Pulire termostati e prese d'aria", "Tutta la casa", 20),
         ("Pulire i tappeti grandi", "Soggiorno", 45),
     ]},
    {"mese": 11, "titolo": "Pulizie profonde pre-feste",
     "focus": "alleggerirsi prima del periodo più intenso dell'anno",
     "attivita": [
         ("Pulire forno e microonde", "Cucina", 40),
         ("Lavare i vetri per la massima luminosità", "Tutta la casa", 40),
         ("Organizzare il soggiorno e gli spazi conviviali", "Soggiorno", 35),
         ("Decluttering degli oggetti inutilizzati", "Tutta la casa", 30),
     ]},
    {"mese": 12, "titolo": "Mantenimento intelligente",
     "focus": "praticità e ordine immediato",
     "attivita": [
         ("Lavare strofinacci, tovaglie e tessuti della cucina", "Cucina", 25),
         ("Tenere libera la cucina per pranzi e cene", "Cucina", 20),
     ]},
]

NOMI_MESI = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
             "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]


def catalogo():
    """Tutte le attivita' in un unico elenco, nella forma della tabella `chores`."""
    voci = []
    for nome, area, minuti in QUOTIDIANE:
        voci.append({"name": nome, "area": area, "frequency": "giornaliera",
                     "minutes": minuti, "month": None})
    for nome, area, minuti in SETTIMANALI:
        voci.append({"name": nome, "area": area, "frequency": "settimanale",
                     "minutes": minuti, "month": None})
    for nome, area, minuti in MENSILI:
        voci.append({"name": nome, "area": area, "frequency": "mensile",
                     "minutes": minuti, "month": None})
    for blocco in STAGIONALI:
        for nome, area, minuti in blocco["attivita"]:
            voci.append({"name": nome, "area": area, "frequency": "stagionale",
                         "minutes": minuti, "month": blocco["mese"]})
    return voci


def mesi():
    """Il calendario annuale, con il titolo e il focus di ogni mese."""
    return [{"mese": b["mese"], "nome": NOMI_MESI[b["mese"]], "titolo": b["titolo"],
             "focus": b["focus"]}
            for b in STAGIONALI]


# --------------------------------------------------------------- scadenze

def _data(valore):
    """Una data ISO dal database, o None se assente/illeggibile."""
    if not valore:
        return None
    try:
        return date.fromisoformat(str(valore)[:10])
    except ValueError:
        return None


def scadenza(frequency, ultima, oggi, month=None):
    """Quando rifare un'attivita'.

    `ultima` e `oggi` sono date (o stringhe ISO). `giorni` e' quanti giorni
    mancano alla prossima volta: negativo se si e' in ritardo, None se non c'e'
    una data (mai fatta, oppure attivita' stagionale).
    """
    ultima_d = _data(ultima)
    oggi_d = _data(oggi) or date.today()
    stato = {"ultima": ultima_d.isoformat() if ultima_d else None,
             "mai_fatta": ultima_d is None, "prossima": None,
             "giorni": None, "in_scadenza": True, "mese": month}

    if frequency == "stagionale":
        # una volta l'anno, nel suo mese: e' in scadenza se il mese e' questo e
        # non risulta gia' fatta quest'anno
        stato["in_scadenza"] = bool(month) and oggi_d.month == month and (
            ultima_d is None or ultima_d.year < oggi_d.year)
        return stato

    if ultima_d is None:
        return stato

    cadenza = CADENZE.get(frequency, 7)
    prossima = ultima_d + timedelta(days=cadenza)
    stato["prossima"] = prossima.isoformat()
    stato["giorni"] = (prossima - oggi_d).days
    stato["in_scadenza"] = oggi_d >= prossima
    return stato


def piano(attivita, ultime, oggi, giorno_pulizie=5):
    """Cosa c'e' da fare adesso e cosa c'e' da fare questo mese.

    La distinzione e' il cuore del metodo: mensili e stagionali non si fanno tutte
    oggi, si distribuiscono nel mese ("ogni mese affronta un ambiente in
    profondita'"). Metterle nel piano di oggi gonfierebbe la giornata a centinaia
    di minuti e il piano verrebbe abbandonato — e' il motivo per cui l'articolo
    dice di non pianificare compiti impossibili. Quindi:

    - `oggi`: le quotidiane (sempre, sono la routine) e le settimanali scadute o
      dovute perche' oggi e' il giorno fisso scelto.
    - `mese`: mensili e stagionali in scadenza, con il focus del mese corrente.
    """
    oggi_d = _data(oggi) or date.today()
    oggi_gruppi = {"quotidiane": [], "settimanali": []}
    mese_gruppi = {"mensili": [], "stagionali": []}
    chiave = {"giornaliera": "quotidiane", "settimanale": "settimanali",
              "mensile": "mensili", "stagionale": "stagionali"}

    for voce in attivita:
        if not voce.get("active", 1):
            continue
        freq = voce.get("frequency")
        gruppo = chiave.get(freq)
        if not gruppo:
            continue
        stato = scadenza(freq, ultime.get(voce["id"]), oggi_d, voce.get("month"))
        dentro = True
        if freq == "settimanale":
            dentro = stato["in_scadenza"] or oggi_d.weekday() == giorno_pulizie
        elif freq in ("mensile", "stagionale"):
            dentro = stato["in_scadenza"]
        if not dentro:
            continue
        fatto_oggi = stato["ultima"] == oggi_d.isoformat()
        # una voce gia' fatta oggi resta visibile ma non conta piu' nel tempo
        voce_stato = {**voce, **stato, "fatto_oggi": fatto_oggi}
        if freq in ("giornaliera", "settimanale"):
            oggi_gruppi[gruppo].append(voce_stato)
        else:
            mese_gruppi[gruppo].append(voce_stato)

    for elenco in (oggi_gruppi | mese_gruppi).values():
        elenco.sort(key=lambda v: (v["fatto_oggi"], v["area"], v["name"]))

    da_fare = [v for elenco in oggi_gruppi.values() for v in elenco if not v["fatto_oggi"]]
    # il focus del mese e' il senso del blocco stagionale: senza il titolo, le
    # attivita' di novembre sembrano uguali a quelle di aprile
    corrente = next((m for m in mesi() if m["mese"] == oggi_d.month), None)
    return {
        "data": oggi_d.isoformat(),
        "giorno": GIORNI_SETTIMANA[oggi_d.weekday()],
        "giorno_pulizie": oggi_d.weekday() == giorno_pulizie,
        "gruppi": oggi_gruppi,
        "mese": {**mese_gruppi, "nome": corrente["nome"] if corrente else "",
                 "titolo": corrente["titolo"] if corrente else "",
                 "focus": corrente["focus"] if corrente else ""},
        "da_fare": len(da_fare),
        "fatto_oggi": sum(1 for elenco in oggi_gruppi.values()
                          for v in elenco if v["fatto_oggi"]),
        # solo stime: il tempo impiegato davvero lo registra il timer e lo mostra
        # /api/chores/summary. Sommare qui le due cose darebbe un numero che non
        # e' ne' il previsto ne' il fatto.
        "minuti_previsti": sum(v.get("minutes") or 0 for v in da_fare),
        "mese_da_fare": sum(1 for elenco in mese_gruppi.values()
                            for v in elenco if not v["fatto_oggi"]),
        "mese_minuti": sum(v.get("minutes") or 0 for elenco in mese_gruppi.values()
                           for v in elenco if not v["fatto_oggi"]),
    }