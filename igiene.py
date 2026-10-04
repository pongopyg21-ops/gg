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

from datetime import date, datetime, time, timedelta

# ------------------------------------------------------------------ costanti

# La cadenza in giorni di ogni blocco. "stagionale" non ha una cadenza vera:
# si fa una volta l'anno, nel mese indicato, e il conto lo fa `scadenza`.
# "frazionaria" e' l'unica che ammette mezze giornate (vedi `FRAZIONARIA`).
CADENZE = {"giornaliera": 1, "frazionaria": 1.5, "settimanale": 7, "mensile": 30}

# La cadenza di "ogni giorno e mezzo". Mezza giornata conta: con 1 o 2 giorni
# tondi non sarebbe ne' "ogni giorno" ne' "ogni giorno e mezzo". Il conto usa
# l'ora del completamento, non solo la data, altrimenti la mezza giornata si
# perde e la cadenza diventa giornaliera (vedi `scadenza`).
FRAZIONARIA = 1.5

FREQUENZE = [
    {"key": "giornaliera", "label": "Ogni giorno", "giorni": 1},
    {"key": "frazionaria", "label": "Ogni giorno e mezzo", "giorni": FRAZIONARIA},
    {"key": "settimanale", "label": "Ogni settimana", "giorni": 7},
    {"key": "mensile", "label": "Ogni mese", "giorni": 30},
    {"key": "stagionale", "label": "Una volta l'anno", "giorni": None},
]


def cadenza_lavatrice(bucati_giorno) -> float:
    """Ogni quanto rimettere in moto la lavatrice, dai bucati al giorno.

    Il legame e' diretto: chi fa due bucati al giorno non aspetta un giorno e
    mezzo, chi ne fa uno ogni tre giorni non deve vederla comparire ogni sera.
    Un valore non dichiarato (0, o qualunque cosa non sia un intero da 1 a 5)
    lascia la cadenza di partenza, 1,5 giorni, che e' il caso piu' comune.

    Il minimo e' mezza giornata: sotto non e' piu' "rifare il bucato", e' tenerlo
    sempre acceso, e la voce resterebbe in cima al piano per sempre.
    """
    try:
        bucati = int(bucati_giorno)
    except (TypeError, ValueError):
        return FRAZIONARIA
    if bucati < 1:
        return FRAZIONARIA
    return max(0.5, round(1.0 / bucati, 2))


AMBIENTI = ["Cucina", "Bagno", "Camere", "Soggiorno", "Ingresso",
            "Esterni", "Ripostigli", "Tutta la casa"]

# Quanti bucati al giorno si possono dichiarare, per l'onboarding e il Profilo.
# 0 non e' un'opzione dell'elenco: e' l'assenza di dichiarazione, e in quel caso
# la lavatrice resta alla cadenza di partenza.
BUCATI_OPZIONI = [1, 2, 3, 4, 5]

GIORNI_SETTIMANA = ["lunedì", "martedì", "mercoledì", "giovedì",
                    "venerdì", "sabato", "domenica"]

# ---------------------------------------------------- blocchi per frequenza
# (nome, ambiente, minuti stimati). I minuti servono a far vedere quanto costa
# il piano di oggi prima di iniziare: e' il senso della regola dei 15 minuti.

# Il budget della giornata: la routine fissa deve restare sotto i venticinque
# minuti, altrimenti diventa un lavoro e non una routine, e il piano si
# abbandona. Le quotidiane sono **tre**: le voci che dicevano la stessa cosa
# ("Riordino generale" e "Raccogliere gli oggetti fuori posto": entrambe
# rimettere a posto per la casa) sono state unite, e "Arieggiare le stanze" e'
# stata tolta — e' aprire le finestre mentre si fa altro, non un lavoro da
# spuntare, e gonfiava la giornata di una voce che non si sente come tale.
QUOTIDIANE = [
    ("Riordino generale", "Tutta la casa", 5),
    ("Piatti e superfici della cucina", "Cucina", 10),
    ("Bagno fresco: lavandino e specchio", "Bagno", 5),
]

# Cadenza "ogni giorno e mezzo": non ha un blocco tondo come le altre, ma una
# voce sola. L'ora del completamento conta (vedi `FRAZIONARIA`), quindi una
# lavatrice messa alle 8 di lunedi' chiede di rifarla verso le 20 di martedi'.
# La cadenza vera la decide il numero di bucati dichiarato in casa (vedi
# `cadenza_lavatrice`): 1,5 giorni e' il valore di partenza.
FRAZIONARIE = [
    ("Avviare la lavatrice", "Bagno", 5),
]

# Il nome della voce del bucato: serve a legare la cadenza ai bucati al giorno
# senza toccare le altre voci frazionarie che l'utente puo' aggiungere.
LAVATRICE = "Avviare la lavatrice"

# L'ordine conta: le settimanali si distribuiscono dal giorno scelto
# dall'utente (`chore_day`) a ritroso, dalla piu' pesante alla piu' leggera. Si
# parte dal piu' pesante perche' e' quella che merita il giorno scelto; le altre
# riempiono i giorni precedenti, una per giorno. Prima entravano **tutte** nello
# stesso giorno, che arrivava a cento minuti di soli settimanali.
SETTIMANALI = [
    ("Aspirare e lavare i pavimenti", "Tutta la casa", 30),
    ("Pulire il bagno in profondità", "Bagno", 25),
    ("Pulire la cucina a fondo", "Cucina", 20),
    ("Spolverare", "Tutta la casa", 15),
    ("Cambiare le lenzuola", "Camere", 10),
]

# Voci tolte dal catalogo dopo essere gia' state seminate, con la voce che le ha
# assorbite (o `None` se sono solo da togliere): restano nel database di chi usa
# l'app da prima e vanno tolte, altrimenti convivono con la loro sostituta (era
# il caso di "Raccogliere gli oggetti fuori posto", unita a "Riordino
# generale"). La sostituta serve a spostarci i completamenti: sono lavoro che
# l'utente ha fatto davvero, e cancellarli sarebbe una perdita silenziosa.
# "Arieggiare le stanze" non ha sostituta: non era un lavoro, e i suoi
# completamenti non hanno senso su nessun'altra voce.
RIMOSSE = {"Raccogliere gli oggetti fuori posto": "Riordino generale",
           "Arieggiare le stanze": None}

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
    for nome, area, minuti in FRAZIONARIE:
        voci.append({"name": nome, "area": area, "frequency": "frazionaria",
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


def _momento(valore):
    """Data e ora di un valore ISO, o None se assente/illeggibile.

    Serve alle cadenze frazionarie, dove mezza giornata conta: `chore_log.date`
    e' un istante ISO (`datetime('now')`), quindi porta l'ora. Un valore con la
    sola data resta leggibile, a mezzanotte.
    """
    if not valore:
        return None
    try:
        return datetime.fromisoformat(str(valore)[:19])
    except ValueError:
        giorno = _data(valore)
        return datetime.combine(giorno, time()) if giorno else None


def scadenza(frequency, ultima, oggi, month=None, cadenza=None):
    """Quando rifare un'attivita'.

    `ultima` e `oggi` sono date (o istanti ISO). `giorni` e' quanti giorni
    mancano alla prossima volta: negativo se si e' in ritardo, None se non c'e'
    una data (mai fatta, oppure attivita' stagionale). Per le cadenze
    frazionarie `giorni` puo' essere una frazione: la mezza giornata si conta in
    ore, altrimenti andrebbe persa (vedi `FRAZIONARIA`).

    `cadenza` scavalca il valore fisso della frequenza, per le voci la cui
    cadenza dipende da una scelta dell'utente (la lavatrice, dai bucati al
    giorno: vedi `cadenza_lavatrice`). None significa "usa quella della
    frequenza".
    """
    ultima_d = _data(ultima)
    oggi_d = _data(oggi) or date.today()
    # la cadenza effettiva entra nello stato: la lavatrice la cambia coi bucati
    # al giorno, e l'interfaccia la mostra per dire ogni quanto tocca davvero
    cadenza = cadenza if cadenza is not None else CADENZE.get(frequency, 7)
    stato = {"ultima": ultima_d.isoformat() if ultima_d else None,
             "mai_fatta": ultima_d is None, "prossima": None,
             "giorni": None, "in_scadenza": True, "mese": month,
             "cadenza_giorni": cadenza}

    if frequency == "stagionale":
        # una volta l'anno, nel suo mese: e' in scadenza se il mese e' questo e
        # non risulta gia' fatta quest'anno
        stato["in_scadenza"] = bool(month) and oggi_d.month == month and (
            ultima_d is None or ultima_d.year < oggi_d.year)
        return stato

    if ultima_d is None:
        return stato

    # Una cadenza frazionaria (un giorno e mezzo) non cade sulla mezzanotte: il
    # giorno in piu' non basta a dire "e mezzo". Si usa l'ora del completamento e
    # si conta in ore, altrimenti alle 8 di lunedi' la voce risulterebbe da
    # rifare gia' martedi' mattina — una cadenza di un giorno, non di uno e mezzo.
    if frequency == "frazionaria":
        ultima_t = _momento(ultima)
        if ultima_t is not None:
            # Il confronto e' fra istanti: se il chiamante ha dato un istante
            # esplicito si usa quello (serve ai test per non dipendere dall'ora
            # vera), altrimenti l'ora corrente. Con la sola data il confronto
            # cadrebbe a mezzanotte e la mezza giornata si perderebbe di nuovo.
            testo_oggi = str(oggi)
            oggi_t = _momento(testo_oggi) if len(testo_oggi) > 10 else None
            if oggi_t is None:
                oggi_t = datetime.now() if not isinstance(oggi, datetime) else oggi
            prossima = ultima_t + timedelta(days=cadenza)
            stato["prossima"] = prossima.isoformat()
            stato["giorni"] = (prossima - oggi_t).total_seconds() / 86400
            stato["in_scadenza"] = oggi_t >= prossima
            return stato

    prossima = ultima_d + timedelta(days=cadenza)
    stato["prossima"] = prossima.isoformat()
    stato["giorni"] = (prossima - oggi_d).days
    stato["in_scadenza"] = oggi_d >= prossima
    return stato


def giorni_settimanali(attivita, giorno_pulizie=5):
    """A quale giorno della settimana tocca ogni settimanale attiva.

    La piu' pesante resta nel giorno scelto dall'utente, che cosi' conserva il
    suo significato; le altre si dispongono nei giorni precedenti, una per
    giorno, dalla piu' pesante alla piu' leggera. Prima entravano tutte nello
    stesso giorno: il sabato arrivava a cento minuti di soli settimanali, oltre
    alla routine, ed e' il motivo per cui il piano veniva abbandonato.

    Le voci aggiunte dall'utente non hanno un posto nel catalogo e finiscono in
    coda all'ordine: riempiono i giorni che restano, invece di ammassarsi tutte
    nel giorno scelto.
    """
    ordine = {nome: i for i, (nome, _area, _minuti) in enumerate(SETTIMANALI)}
    settimanali = sorted(
        (v for v in attivita
         if v.get("frequency") == "settimanale" and v.get("active", 1)),
        key=lambda v: (ordine.get(v["name"], len(SETTIMANALI)), v["name"]),
    )
    return {v["id"]: (giorno_pulizie - i) % 7 for i, v in enumerate(settimanali)}


def piano(attivita, ultime, oggi, giorno_pulizie=5, giorni=None, bucati_giorno=0):
    """Cosa c'e' da fare adesso e cosa c'e' da fare questo mese.

    La distinzione e' il cuore del metodo: mensili e stagionali non si fanno tutte
    oggi, si distribuiscono nel mese ("ogni mese affronta un ambiente in
    profondita'"). Metterle nel piano di oggi gonfierebbe la giornata a centinaia
    di minuti e il piano verrebbe abbandonato — e' il motivo per cui l'articolo
    dice di non pianificare compiti impossibili. Quindi:

    - `oggi`: le quotidiane (sempre, sono la routine), le frazionarie (sempre,
      ma con lo stato che dice se tocca) e le settimanali che tocca oggi, piu'
      quelle scadute (in ritardo nonostante la distribuzione). La distribuzione
      sui giorni e' in `giorni_settimanali`: senza, le settimanali si
      ammassavano tutte nel giorno fisso.
    - `mese`: mensili e stagionali in scadenza, con il focus del mese corrente.
    """
    oggi_d = _data(oggi) or date.today()
    oggi_gruppi = {"quotidiane": [], "frazionarie": [], "settimanali": []}
    mese_gruppi = {"mensili": [], "stagionali": []}
    chiave = {"giornaliera": "quotidiane", "frazionaria": "frazionarie",
              "settimanale": "settimanali",
              "mensile": "mensili", "stagionale": "stagionali"}
    if giorni is None:
        giorni = giorni_settimanali(attivita, giorno_pulizie)

    for voce in attivita:
        if not voce.get("active", 1):
            continue
        freq = voce.get("frequency")
        gruppo = chiave.get(freq)
        if not gruppo:
            continue
        # la lavatrice non ha una cadenza fissa: dipende dai bucati al giorno
        # dichiarati in casa (vedi `cadenza_lavatrice`)
        cadenza = (cadenza_lavatrice(bucati_giorno)
                   if freq == "frazionaria" and voce.get("name") == LAVATRICE else None)
        stato = scadenza(freq, ultime.get(voce["id"]), oggi_d, voce.get("month"),
                         cadenza=cadenza)
        dentro = True
        if freq == "settimanale":
            # Tocca oggi, oppure e' in ritardo perche' il suo giorno e' stato
            # saltato. Una voce mai fatta viene mostrata nel suo giorno e non
            # subito: al primo uso altrimenti rientrerebbero tutte insieme, che
            # e' esattamente l'ammasso che la distribuzione deve togliere.
            dentro = (giorni.get(voce["id"]) == oggi_d.weekday()
                      or (not stato["mai_fatta"] and stato["in_scadenza"]))
        elif freq == "frazionaria":
            # Come le settimanali, ma senza un giorno fisso: in elenco quando e'
            # davvero da rifare (o mai fatta). Fuori quando non tocca ancora, per
            # non gonfiare il "da fare" di oggi con una lavatrice non dovuta; nel
            # frattempo resta visibile in Routine e nel catalogo.
            dentro = stato["in_scadenza"]
        elif freq in ("mensile", "stagionale"):
            dentro = stato["in_scadenza"]
        if not dentro:
            continue
        # una voce fatta oggi resta visibile ma non conta piu' nel tempo. Si
        # confronta la **data**: per le frazionarie `ultima` porta anche l'ora.
        fatto_oggi = bool(stato["ultima"]) and stato["ultima"][:10] == oggi_d.isoformat()
        voce_stato = {**voce, **stato, "fatto_oggi": fatto_oggi, "cadenza": cadenza}
        if freq == "settimanale":
            # il giorno assegnato serve all'interfaccia per dire "tocca giovedi'"
            # e all'utente per sapere quando aspettarsela
            assegnato = giorni.get(voce["id"])
            voce_stato["giorno_settimanale"] = assegnato
            voce_stato["giorno_settimanale_nome"] = (
                GIORNI_SETTIMANA[assegnato] if assegnato is not None else None)
            voce_stato["giorno_settimanale_oggi"] = assegnato == oggi_d.weekday()
        if freq in ("giornaliera", "frazionaria", "settimanale"):
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
        # com'e' divisa la settimana: serve all'interfaccia per mostrare che le
        # settimanali non sono tutte oggi, e all'utente per sapere che giorno e'
        "settimana": [
            {"giorno": i, "nome": GIORNI_SETTIMANA[i],
             "oggi": i == oggi_d.weekday(),
             "minuti": sum(v.get("minutes") or 0 for v in attivita
                           if v.get("active", 1) and v.get("frequency") == "settimanale"
                           and giorni.get(v["id"]) == i)}
            for i in range(7)
        ],
        "settimanali_oggi": len(oggi_gruppi["settimanali"]),
    }