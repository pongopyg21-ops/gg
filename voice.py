"""Comandi vocali: dalla frase dettata al comando strutturato.

Il riconoscimento vocale avviene nel browser (Web Speech API), che restituisce
solo testo: qui quel testo diventa un comando per l'app. Tenere la comprensione
sul server permette di verificarla con dei test, senza microfono.

Esempi di frasi riconosciute:

    "aggiungi due chili di farina alla dispensa"  -> dispensa, farina, 2 kg
    "metti il latte nella spesa"                  -> spesa, latte, 1 pz
    "aggiungi il sapone al magazzino"             -> magazzino, sapone
    "metti il detersivo in cantina"               -> magazzino, detersivo
    "sono allergico al nichel"                    -> allergia, nichel
    "cerca la carbonara"                          -> ricerca ricetta
"""
import re
import unicodedata

import allergens

# unità riconosciute per token -> unità dell'app. "etto" è un caso a parte:
# vale 100 g e viene convertito subito, così in dispensa arriva sempre in grammi.
_UNIT_TOKENS = {
    "g": "g", "gr": "g", "grammo": "g", "grammi": "g",
    "etto": "etto", "etti": "etto", "hg": "etto",
    "kg": "kg", "chilo": "kg", "chili": "kg", "chilogrammo": "kg", "chilogrammi": "kg",
    "ml": "ml", "millilitro": "ml", "millilitri": "ml",
    "l": "l", "litro": "l", "litri": "l",
    "cucchiaio": "cucchiaio", "cucchiai": "cucchiaio",
    "cucchiaino": "cucchiaino", "cucchiaini": "cucchiaino",
    "pz": "pz", "pezzo": "pz", "pezzi": "pz", "unita": "pz",
    "confezione": "confezione", "confezioni": "confezione",
    "pacco": "confezione", "pacchi": "confezione",
    "fetta": "fetta", "fette": "fetta",
}

# dove va la voce dettata
_DEST_TOKENS = {
    "dispensa": "pantry",
    "spesa": "shopping", "lista": "shopping", "carrello": "shopping",
    "supermercato": "shopping", "mercato": "shopping", "negozio": "shopping",
    "allergia": "term", "allergie": "term", "intolleranza": "term",
    "intolleranze": "term", "restrizioni": "term",
    "magazzino": "storage", "provviste": "storage",
    "scorte": "storage", "scorta": "storage",
}

# Il magazzino non si nomina solo con la parola "magazzino": si dice anche dove
# sta la roba ("in garage", "in cantina"). Il luogo e' un indizio forte ma non
# una destinazione esplicita: "in cucina" e' anche il posto della dispensa,
# quindi vale solo se la frase non nomina gia' una destinazione.
_LUOGO_TOKENS = {
    "garage": "Garage", "cantina": "Cantina", "soffitta": "Soffitta",
    "ripostiglio": "Ripostiglio", "solaio": "Soffitta", "magazzino": "Ripostiglio",
    "balcone": "Balcone", "terrazzo": "Balcone", "bagno": "Bagno",
    "box": "Garage", "taverna": "Cantina",
}

# parola tipica di un oggetto di magazzino: sapone, detersivo, candeggina...
# Serve a sciogliere il caso in cui la frase non dice dove va la cosa. Il test
# e' per parola intera, cosi' "saponetta" non conta come "sapone".
_MAGAZZINO_PAROLE = {
    "sapone", "saponi", "saponetta", "saponette", "detersivo", "detersivi",
    "candeggina", "ammorbidente", "brillantante", "disinfettante",
    "anticalcare", "sgrassatore", "spugna", "spugne", "panno", "panni",
    "sacchi", "sacchetto", "sacchetti", "cartaigienica", "fazzoletti",
    "tovagliolini", "rotolone", "scottex", "sturalavandini", "scopino",
    "candela", "candele", "pile", "batteria", "batterie", "lampadina",
    "lampadine", "neon", "viti", "vite", "chiodi", "chiodo", "tasselli",
    "bulloni", "nastro", "nastri", "colla", "silicone",
    "guanti", "guanto", "rasoi", "rasoio", "lame", "spazzolino",
    "spazzolini", "dentifricio", "dentifrici", "shampoo", "bagnoschiuma",
    "deodorante", "assorbenti", "cotton", "cerotti", "garze", "termometro",
}

_UNITS_WORDS = {
    "zero": 0, "uno": 1, "un": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4,
    "cinque": 5, "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10,
    "undici": 11, "dodici": 12, "tredici": 13, "quattordici": 14, "quindici": 15,
    "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19,
    "venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50, "sessanta": 60,
    "settanta": 70, "ottanta": 80, "novanta": 90, "cento": 100,
}
_FRACTIONS = {"mezzo": 0.5, "mezza": 0.5, "meta": 0.5, "quarto": 0.25}


def _build_numbers():
    """Numeri fino a 999 come si pronunciano: venticinque, centotto, duecento."""
    numeri = dict(_UNITS_WORDS)
    unita = [(k, v) for k, v in _UNITS_WORDS.items() if 0 < v < 10]
    decine = [(k, v) for k, v in _UNITS_WORDS.items() if v >= 20 and v % 10 == 0]

    # le decine perdono la vocale finale davanti a uno e otto: ventuno, ventotto
    for d, dv in decine:
        for u, uv in unita:
            radice = d[:-1] if u in ("uno", "otto") else d
            numeri[radice + u] = dv + uv

    # le centinaia fanno eccezione: primo il moltiplicatore, poi "cento"
    # (duecento), oppure "cento" che si elide davanti a vocale (centotto)
    for u, uv in unita:
        numeri[u + "cento"] = uv * 100
    for parola, valore in list(numeri.items()):
        if valore >= 100 or valore == 0:
            continue
        radice = "cento" if valore >= 10 or parola[0] not in "aeiou" else "cent"
        numeri[radice + parola] = 100 + valore
        numeri["cento" + parola] = 100 + valore
    numeri["mille"] = 1000
    return numeri


_NUMBERS = _build_numbers()

# verbi di comando: la loro presenza distingue una richiesta da una frase detta a caso
_COMMAND_VERBS = {"aggiungi", "aggiungere", "aggiungimi", "metti", "mettere",
                  "inserisci", "inserire", "segna", "segnami", "ricordami",
                  "ricorda", "voglio", "vorrei", "vorrebbe", "vorrebbero",
                  "dovrei", "dovremmo", "devo", "dobbiamo", "comprare",
                  "comperare", "manca", "mancano", "serve", "servono",
                  "servirebbe", "servirebbero", "bisogna"}

# parole che non fanno parte del nome dell'ingrediente
_STOPWORDS = {
    "aggiungi", "aggiungere", "aggiungimi", "metti", "mettere", "inserisci",
    "inserire", "segna", "segnami", "ricordami", "ricorda", "voglio", "vorrei",
    "vorrebbe", "vorrebbero", "servirebbe", "servirebbero", "dovrei", "dovremmo",
    "devo", "dobbiamo", "comprare", "comperare", "manca", "mancano", "serve",
    "servono", "di", "del", "dello", "della", "dei", "degli", "delle", "da",
    "dal", "dallo", "dalla", "dai", "dagli", "dalle", "a", "al", "allo", "alla",
    "ai", "agli", "alle", "in", "nel", "nello", "nella", "nei", "negli", "nelle",
    "il", "lo", "la", "i", "gli", "le", "e", "ed", "con", "per", "su", "sul",
    "sullo", "sulla", "circa", "un", "uno", "una", "questo", "questa", "quello",
    "quella", "mi", "ci", "ho", "sono", "allergico", "allergica", "intollerante",
    "intolleranti",
}

# per la ricerca ricetta si tolgono le parole di comando e i riempitivi: il
# resto è il testo da cercare, che il client confronta parola per parola
_SEARCH_WORDS = {"cerca", "cercami", "cercare", "cercavo", "cercando", "mostrami",
                 "trova", "trovami", "fammi", "vedere", "la", "il", "lo", "le",
                 "i", "gli", "un", "una", "ricetta", "ricette", "per", "di", "da",
                 "con", "che", "dei", "delle", "della", "del", "al", "allo", "alla",
                 "ai", "agli", "alle", "a", "e", "ed", "o", "mangiare", "cucinare"}

# Creazione di una ricetta. Serve una parola che dica "ricetta" **e** un verbo
# che dica "nuova": "aggiungi" da solo è una spesa, "ricetta" da sola è una
# ricerca. Insieme sono una ricetta da scrivere.
_RECIPE_WORDS = {"ricetta", "ricette"}
_RECIPE_VERBS = {"crea", "creare", "creami", "creo", "nuova", "nuovo", "aggiungi",
                 "aggiungere", "aggiungimi", "salva", "salvare", "inserisci",
                 "inserire", "scrivi", "scrivere", "registra", "registrare",
                 "prepara", "preparami", "preparare"}
# parole che non fanno parte del nome della ricetta. Volutamente NON contiene
# le preposizioni: "pasta al forno" e "risotto ai funghi" le preposizioni ce le
# hanno dentro. Si tolgono invece ai bordi, in `_nome_ricetta`, dove sono
# avanzi del discorso ("...per la carbonara") e non parte del nome.
_RECIPE_FILLER = _RECIPE_VERBS | _RECIPE_WORDS | {
    "chiamata", "chiamato", "nome", "intitolata", "come", "tu", "puoi", "potresti",
    "ho", "voglio", "vorrei",
}

# avanzi attorno al nome di un ingrediente dettato: "500 grammi **di** pasta",
# "**e** 300 grammi di pomodoro". Non contiene le preposizioni che possono far
# parte di un nome ("passata di pomodoro", "olio di oliva"): si tolgono solo ai
# bordi, e lì sono avanzi del discorso.
_INGREDIENTE_SCARTO = {
    "di", "del", "dello", "della", "dei", "degli", "delle", "da", "dal", "dallo",
    "dalla", "a", "al", "allo", "alla", "ai", "agli", "alle", "in", "nel",
    "con", "e", "ed", "circa", "un", "uno", "una", "il", "lo", "la", "i", "gli",
    "le", "mezzo", "mezza", "meta",
}

# Una ricetta **cucinata**: "ho cucinato pasta al sugo". Non si crea niente, si
# scala dalla dispensa quello che e' stato consumato.
#   Il verbo vuole l'ausiliare al passato ("ho", "avevo", ...). Senza, "pasta
#   cucinata" e' un participio usato come aggettivo e una frase qualsiasi
#   ("la pasta cucinata ieri") basterebbe a far sparire mezza dispensa.
_COOKED_VERBS = {"cucinato", "cucinata", "cucinati", "cucinate",
                 "preparato", "preparata", "preparati", "preparate",
                 "cotto", "cotta", "cotti", "cotte"}
_COOKED_AUSILIARI = {"ho", "hai", "ha", "abbiamo", "avete", "hanno",
                     "avevo", "avevi", "aveva", "avevamo", "avevate", "avevano"}
# avanzi di discorso che non fanno parte del nome: si tolgono ai bordi, mai
# dentro: "pasta al sugo" e "risotto ai funghi" le preposizioni ce le hanno.
_COOKED_SCARTO = {"oggi", "ieri", "adesso", "ora", "appena", "pure", "anche",
                  "solo", "per", "cena", "pranzo", "colazione", "poco", "fa",
                  "di", "da", "a", "in", "su", "con"}

# Le domande non sono ordini.
# "che cosa c'e' in dispensa" contiene "dispensa" e "c'e'", che sono anche
# parole di un comando, e senza questo veniva eseguita: l'app rispondeva
# "Fatto. Che cosa c'e in dispensa, 1 pz" e **scriveva quella voce in dispensa**.
# Una domanda a cui si risponde sbagliando e' peggio di una domanda senza
# risposta: la voce di troppo resta li' per sempre.
#
# L'avvio e' una parola interrogativa **all'inizio** della frase: cosi' non
# colpisce "metti il sale, che serve" o "vorrei sapere se c'e' il latte", dove
# la frase resta un comando. "quanto" da solo non basta ("quanto sale serve"
# e' una domanda, ma "quanto sale" senza verbo sarebbe ambiguo) e viene
# accoppiato alle parole che seguono.
_DOMANDA_AVVIO = re.compile(
    r"^(che|cosa|cos|quale|quali|quanti|quante|quanto|quanta|dove|come|chi"
    r"|mi (?:dici|sai dire|chiedo|domando)|dimmi|dimmelo|sai|sapresti|sapete"
    r"|(?:vorrei|voglio|volevo|potrei|puoi|potresti) (?:sapere|sapendo|dirmi|saper)"
    r"|hai|avete|avremmo|c'e|ci sono|si puo|si possono)\b")

# con quale parte dell'app ha a che fare la domanda: decide cosa cercare
_DOMANDA_LUOGHI = {
    "pantry": {"dispensa", "dispense", "cantina", "ripostiglio"},
    "shopping": {"spesa", "lista", "carrello", "supermercato", "mercato", "negozio"},
    "storage": {"magazzino", "garage", "soffitta", "solaio", "box", "taverna",
                "provviste", "scorte", "balcone", "terrazzo", "bagno"},
    "recipes": {"ricetta", "ricette", "cucina", "mangiare", "cucinare", "piatto",
                "piatti", "pranzo", "cena"},
    "chores": {"pulizia", "pulizie", "faccende", "casa", "lavare", "pulire"},
    "profile": {"profilo", "allergia", "allergie", "intolleranza", "intolleranze",
                "restrizioni"},
}


def _domanda(normalized):
    """Cosa vuole sapere una domanda: la parte dell'app e l'argomento cercato.

    Ritorna `(area, argomento)`, con area `None` se non si capisce dove
    guardare: in quel caso e' meglio non rispondere che rispondere a caso.
    """
    if not _DOMANDA_AVVIO.match(normalized):
        return None, ""
    tokens = normalized.split()
    for area, parole in _DOMANDA_LUOGHI.items():
        if parole & set(tokens):
            # le parole della domanda non fanno parte di cio' che si cerca:
            # "che cosa c'e' in dispensa" cerca il vuoto, non "dispensa"
            resto = [t for t in tokens if t not in parole and t not in _PAROLE_DOMANDA]
            return area, " ".join(resto).strip()

    # Nessun luogo detto, ma la domanda parla di un alimento: "quanto sale
    # serve", "hai il latte", "c'e' la farina". La risposta sta in dispensa.
    # Senza questo, "quanto sale serve" finiva in lista della spesa: una
    # domanda eseguita come ordine, che e' il modo peggiore di sbagliare.
    resto = [t for t in tokens if t not in _PAROLE_DOMANDA]
    if resto and _DOMANDA_DI_ALIMENTO & set(tokens):
        return "pantry", " ".join(resto).strip()
    return None, ""


# domande su un alimento senza dire dove: la risposta e' in dispensa.
# Sono parole intere e possono stare anche a meta' frase: "vorrei sapere se
# c'e' il latte" e' una domanda quanto "c'e' il latte".
_DOMANDA_DI_ALIMENTO = {"quanto", "quanta", "quanti", "quante", "hai", "avete",
                        "avremmo", "c'e", "ce"}


# parole della domanda stessa: non sono ne' il luogo ne' cio' che si cerca
#   "c'e" resta una parola intera: `_norm` non toglie l'apostrofo, quindi il
#   token e' "c'e", e senza questa voce "che cosa c'e' in dispensa" cercava la
#   stringa "c'e" in dispensa e rispondeva "non c'e' c'e' in dispensa".
_PAROLE_DOMANDA = {
    "che", "cosa", "cos", "quale", "quali", "quanto", "quanta", "quanti", "quante",
    "dove", "come", "chi", "c", "e", "ce", "c'e", "ci", "sono", "in", "nel", "nello",
    "nella", "nei", "negli", "nelle", "il", "lo", "la", "i", "gli", "le", "di",
    "del", "dello", "della", "dei", "degli", "delle", "da", "dal", "dalla", "a",
    "al", "allo", "alla", "ai", "agli", "alle", "su", "sul", "sullo", "sulla",
    "per", "con", "ho", "hai", "abbiamo", "avete", "avremmo", "manca", "mancano",
    "serve", "servono", "rimasto", "rimasti", "rimasta", "rimaste", "ancora",
    "dentro", "fuori", "adesso", "ora", "oggi", "casa", "mia", "mio", "miei",
    "mie", "sto", "stanno", "puo", "puoi", "posso", "potrei", "dirmi",
    "dimmi", "sai", "sapresti", "si", "no", "tutto", "tutta", "tutti", "tutte",
    "qualcosa", "niente", "nulla", "un", "una", "uno", "piu", "meno", "molto",
    "poco", "davvero", "esattamente", "scusa", "scusami", "perfavore", "grazie",
    "devo", "deve", "dobbiamo", "dovrei", "dovremmo", "fare", "faccio", "fatto",
    "sapere", "sapendo", "chiedo", "chiedere", "chiedevo", "se", "forse",
    "invece", "anche", "solo", "proprio", "qui", "qua", "li", "la",
    "vorrei", "voglio", "volevo", "potrei", "potresti", "sapendo",
}


def _norm(text):
    """Minuscolo, senza accenti e senza punteggiatura; l'apostrofo resta."""
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[.,;:!?()\"«»]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _number_at(tokens, i):
    """(valore, token consumati) se all'indice i inizia un numero, altrimenti None.

    Riconosce le cifre, i numeri a parole e le frazioni. "un quarto" è una
    frazione in due parole e va provata **prima** di "un" = 1, altrimenti
    "un quarto di burro" diventerebbe un'unità di burro.
    """
    if i >= len(tokens):
        return None
    tok = tokens[i]

    if tok in ("un", "una", "mezzo", "mezza"):
        next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
        if next_tok in _FRACTIONS:
            return _FRACTIONS[next_tok], 2
    if re.fullmatch(r"\d+(?:[.,]\d+)?", tok):
        return float(tok.replace(",", ".")), 1
    if tok in _NUMBERS:
        return float(_NUMBERS[tok]), 1
    if tok in _FRACTIONS:
        return _FRACTIONS[tok], 1
    return None


def _extract_amount(tokens):
    """(quantità, unità, indici consumati) letti dalla frase.

    Copre anche le forme in cui la frazione segue l'unità ("un chilo e mezzo"),
    perché lì il "mezzo" non è adiacente al numero.
    """
    for i in range(len(tokens)):
        found = _number_at(tokens, i)
        if not found:
            continue
        value, used = found
        consumed = list(range(i, i + used))

        unit = None
        j = i + used
        # l'unità può precedere il numero ("mezzo litro") o seguirlo ("due chili")
        if j < len(tokens) and tokens[j] in _UNIT_TOKENS:
            unit = _UNIT_TOKENS[tokens[j]]
            consumed.append(j)
            j += 1
        elif i > 0 and tokens[i - 1] in _UNIT_TOKENS:
            unit = _UNIT_TOKENS[tokens[i - 1]]
            consumed.append(i - 1)

        # "un chilo e mezzo" / "due litri e un quarto"
        if j < len(tokens) and tokens[j] == "e" and j + 1 < len(tokens):
            frac_token = tokens[j + 1]
            frac = _FRACTIONS.get(frac_token)
            if frac is None and frac_token in ("un", "uno", "una") and j + 2 < len(tokens):
                frac = _FRACTIONS.get(tokens[j + 2])
                if frac is not None:
                    consumed += [j, j + 1, j + 2]
            if frac is not None:
                value += frac
                if not consumed or j not in consumed:
                    consumed += [j, j + 1]
        return value, unit, consumed
    return None, None, []


def _find_destination(tokens):
    """(destinazione, indice, esplicita, luogo). Senza indizi vale la spesa.

    Il magazzino si riconosce in tre modi, dal piu' sicuro al piu' debole:

    1. la parola "magazzino" (o "provviste", "scorte"): esplicito;
    2. un luogo detto nella frase ("in garage", "in cantina"): indicato, ma non
       esplicito, perche' "in cucina" e' anche il posto della dispensa;
    3. la parola stessa dice che e' un oggetto di magazzino ("il sapone", "il
       detersivo"): e' l'indizio piu' debole e vale solo in mancanza di altro.

    L'ordine conta: "aggiungi il sapone in dispensa" resta dispensa, perche' la
    destinazione esplicita vince sulla parola dell'oggetto.
    """
    for i, tok in enumerate(tokens):
        dest = _DEST_TOKENS.get(tok)
        if dest:
            return dest, i, True, _LUOGO_TOKENS.get(tok)

    for i, tok in enumerate(tokens):
        luogo = _LUOGO_TOKENS.get(tok)
        if luogo:
            return "storage", i, False, luogo

    if _MAGAZZINO_PAROLE & set(tokens):
        return "storage", None, False, None

    return "shopping", None, False, None


def _clean_name(tokens, skip):
    """Nome dell'ingrediente, senza le parole di comando.

    Le parole di comando si tolgono solo ai bordi: all'interno possono far parte
    del nome, come in "passata di pomodoro" o "olio extravergine di oliva".
    """
    parole = [t for i, t in enumerate(tokens) if i not in skip]
    while parole and parole[0] in _STOPWORDS:
        parole.pop(0)
    while parole and parole[-1] in _STOPWORDS:
        parole.pop()
    # l'articolo resta attaccato all'apostrofo: "l'acqua" -> "acqua"
    return " ".join(p.split("'", 1)[1] if p.startswith(("l'", "un'", "d'")) and len(p) > 2
                    else p for p in parole if p).strip()


def _nome_ricetta(tokens, ingredienti_da=None):
    """Nome della ricetta dettata, o '' se la frase non ne contiene uno.

    I riempitivi si tolgono da tutta la frase, non solo ai bordi come per gli
    ingredienti: in "crea una ricetta chiamata pasta al forno" il nome sta in
    mezzo e le parole di comando sono sparse. Articoli e preposizioni invece si
    tolgono solo ai bordi: dentro il nome sono parte di esso ("pasta al forno"),
    fuori sono avanzi di discorso ("una ricetta **per la** carbonara").

    `ingredienti_da` è l'indice da cui comincia l'elenco degli ingredienti
    dettati: il nome finisce lì, altrimenti le dosi finirebbero nel titolo.
    """
    if ingredienti_da is not None:
        tokens = tokens[:ingredienti_da]
    parole = [t for t in tokens if t not in _RECIPE_FILLER]
    while parole and parole[0] in _STOPWORDS:
        parole.pop(0)
    while parole and parole[-1] in _STOPWORDS:
        parole.pop()
    return " ".join(parole).strip()


def _numero_con_unita(tokens, i):
    """True se in `tokens[i]` c'è un numero con l'unità attaccata ("500 grammi").

    L'unità è ciò che distingue una dose da una cifra dentro un nome: "torta 7
    vasetti" è un titolo, "500 grammi di pasta" è un ingrediente.
    """
    trovato = _number_at(tokens, i)
    if not trovato:
        return False
    _, usati = trovato
    dopo = i + usati
    if dopo < len(tokens) and tokens[dopo] in _UNIT_TOKENS:
        return True
    return i > 0 and tokens[i - 1] in _UNIT_TOKENS


def _nome_da_ingredienti(tokens):
    """Indice dove finisce il nome della ricetta e comincia l'elenco, o None.

    Due segnali, nell'ordine:

    1. la congiunzione "con" seguita da un numero ("con 4 uova"): è la forma con
       cui si detta un elenco, anche quando la dose è contata e non pesata;
    2. un numero con l'unità ("500 grammi"), che vale anche senza "con".

    Il solo numero non basta: "crea la ricetta torta 7 vasetti" è un titolo, non
    un elenco, e senza questo la ricetta si chiamerebbe "torta".
    """
    for i in range(len(tokens) - 1):
        if tokens[i] == "con" and _number_at(tokens, i + 1):
            return i
    for i in range(len(tokens)):
        if _numero_con_unita(tokens, i):
            if i > 0 and tokens[i - 1] == "con":
                return i - 1
            return i
    return None


def _ingredienti_da_dettato(tokens):
    """Ingredienti dettati in coda a una frase di ricetta.

    "con 500 grammi di pasta e 300 grammi di pomodoro" -> due ingredienti con le
    loro dosi. Si spezza sulla congiunzione "e" e si legge la quantità con
    `_extract_amount`: quello che resta, ripulito, è il nome dell'ingrediente.

    Senza questa lettura le dosi finivano tutte dentro il **nome** della ricetta
    ("pasta al forno con 500 grammi di pasta e 300 grammi di pomodoro"): la voce
    dichiarava di creare una ricetta e ne creava una con un titolo assurdo.
    """
    elenco = []
    pezzo = []
    for tok in tokens + ["e"]:
        if tok == "e":
            elenco += _ingredienti_del_pezzo(pezzo)
            pezzo = []
        else:
            pezzo.append(tok)
    return elenco


def _ingredienti_del_pezzo(pezzo):
    """Uno o più ingredienti da un tratto di frase, spezzando sui numeri nuovi.

    La virgola della dettatura ("guanciale, 4 uova") arriva qui senza virgola,
    quindi un numero che apre dopo un ingrediente già completo è un ingrediente
    nuovo. "pasta 500 grammi" invece resta uno solo: lì il numero completa
    l'ingrediente appena detto, non ne apre un altro.
    """
    fuori = []
    corrente = []
    for tok in pezzo:
        trovato = _number_at([tok], 0)
        deja_completo = corrente and _extract_amount(corrente)[0] is not None
        nuovo_numero = trovato and tok not in _UNIT_TOKENS
        unita_prima = bool(corrente) and corrente[-1] in _UNIT_TOKENS
        if deja_completo and nuovo_numero and not unita_prima:
            fuori.append(corrente)
            corrente = [tok]
        else:
            corrente.append(tok)
    if corrente:
        fuori.append(corrente)

    elenco = []
    for gruppo in fuori:
        nome, quantita, unita = _ingrediente_singolo(gruppo)
        if nome:
            elenco.append({"name": nome, "quantity": quantita, "unit": unita})
    return elenco


def _ingrediente_singolo(pezzo):
    """(nome, quantità, unità) da un pezzo di elenco, tipo "500 grammi di pasta"."""
    quantita, unita, consumati = _extract_amount(pezzo)
    skip = set(consumati)
    parole = [t for i, t in enumerate(pezzo) if i not in skip]
    while parole and parole[0] in _INGREDIENTE_SCARTO:
        parole.pop(0)
    while parole and parole[-1] in _INGREDIENTE_SCARTO:
        parole.pop()
    # l'articolo resta attaccato all'apostrofo, come per gli altri ingredienti
    nome = " ".join(p.split("'", 1)[1] if p.startswith(("l'", "un'", "d'")) and len(p) > 2
                    else p for p in parole if p).strip()
    return nome, quantita, unita


def _nome_cucinato(tokens):
    """Nome della ricetta cucinata, dall'ausiliare in poi.

    Si parte dall'ausiliare e si prende tutto quello che segue: cosi' il nome e'
    quello che si e' detto davvero ("ho cucinato **pasta al sugo**") e non resta
    incollato un verbo di comando detto prima ("aggiungi", "metti"). I verbi
    dell'ausiliare in poi non si toccano, perche' fanno parte del nome.
    """
    inizio = None
    i = 0
    while i < len(tokens):
        if tokens[i] in _COOKED_AUSILIARI:
            # l'ausiliare vale solo se il participio segue a breve: "ho mangiato,
            # poi mi sono preparato" non e' "ho preparato qualcosa"
            for j in range(i + 1, min(i + 4, len(tokens))):
                if tokens[j] in _COOKED_VERBS:
                    inizio = j + 1
                    break
            if inizio is not None:
                break
        i += 1
    if inizio is None:
        return ""

    parole = tokens[inizio:]
    while parole and (parole[0] in _STOPWORDS or parole[0] in _COOKED_SCARTO
                      or parole[0] in _RECIPE_WORDS):
        parole.pop(0)
    while parole and (parole[-1] in _STOPWORDS or parole[-1] in _COOKED_SCARTO):
        parole.pop()
    return " ".join(parole).strip()


def _clean_term(text):
    """Termine di allergia: si prova prima la frase intera, poi si divide.

    "frutta a guscio" e "latte e lattosio" sono etichette uniche: vanno tenute
    intere, altrimenti la divisione su "e"/"a" le spezzerebbe.
    """
    tokens = text.split()
    while tokens and tokens[0] in _STOPWORDS:
        tokens.pop(0)
    while tokens and tokens[-1] in _STOPWORDS:
        tokens.pop()
    frase = " ".join(tokens)
    if not frase:
        return []

    if allergens.resolve(frase):
        return [frase]

    parti = re.split(r"\s+e\s+|\s*,\s*", frase)
    out = []
    for p in parti:
        p = " ".join(t for t in p.split() if t not in _STOPWORDS).strip()
        if p:
            out.append(p)
    return out or [frase]


def _categoria_deducibile(tokens):
    """Categoria del magazzino suggerita dagli indizi della frase.

    Il magazzino ha categorie libere, quindi indovinarla e' un di piu': se non
    si capisce resta "Altro", che e' esattamente quello che l'utente puo'
    correggere a mano. I consumabili (sapone, detersivo) sono la voce piu'
    frequente: finirli in "Altro" costringerebbe a ritrovarli ogni volta.
    """
    if {"detersivo", "detersivi", "sgrassatore", "ammorbidente", "candeggina",
        "anticalcare", "brillantante", "disinfettante", "pulizia"} & set(tokens):
        return "Pulizia casa"
    if {"sapone", "saponi", "saponetta", "saponette", "shampoo", "bagnoschiuma",
        "dentifricio", "dentifrici", "deodorante", "rasoio", "rasoi",
        "spazzolino", "spazzolini", "assorbenti", "cotton"} & set(tokens):
        return "Igiene personale"
    if "cartaigienica" in tokens or ("carta" in tokens and "igienica" in tokens):
        return "Igiene personale"
    if {"vite", "viti", "chiodo", "chiodi", "tassello", "tasselli", "bullone",
        "bulloni", "martello", "cacciavite", "trapano", "chiave", "chiavi",
        "pinza", "pinze"} & set(tokens):
        return "Ferramenta"
    if {"lampadina", "lampadine", "neon", "prolunga", "prolunghe", "pila",
        "pile", "batteria", "batterie", "cavo", "cavi"} & set(tokens):
        return "Elettricita'"
    if {"olio", "aceto", "candela", "candele", "tovagliolini", "sacchetti",
        "cartaforno"} & set(tokens):
        return "Cucina"
    return None


def parse(text):
    """Comando strutturato ricavato dalla frase dettata.

    Ritorna un dizionario con `intent` fra:
    `pantry_add`, `shopping_add`, `storage_add`, `term_add`, `recipe_search`,
    `recipe_add`, `recipe_cooked`, `domanda`, `unknown`.
    """
    raw = str(text or "").strip()
    normalized = _norm(raw)
    base = {"intent": "unknown", "text": raw}
    if not normalized:
        return base

    # Le domande vengono **prima** di tutto il resto: sono la frase che, senza
    # questo ramo, assomiglia di piu' a un comando e fa piu' danno ("che cosa
    # c'e' in dispensa" veniva scritta in dispensa). Un ordine vero non inizia
    # con una parola interrogativa, quindi qui non si perde nessun comando.
    area, argomento = _domanda(normalized)
    if area:
        return {**base, "intent": "domanda", "area": area, "query": argomento}

    # allergie e intolleranze: un termine per il profilo
    if re.search(r"\b(allergi\w*|intolleran\w*|restrizion\w*)\b", normalized):
        terms = _clean_term(normalized)
        if terms:
            return {**base, "intent": "term_add", "terms": terms}

    # Ricetta cucinata: "ho cucinato pasta al sugo". Va **prima** di `recipe_add`
    # perche' "ho preparato una ricetta" contiene anche "prepara" + "ricetta":
    # senza questo ordine una ricetta gia' cucinata aprirebbe il modulo di una
    # ricetta nuova, che e' l'opposto di quello che serve.
    tokens_prova = normalized.split()
    if _COOKED_VERBS & set(tokens_prova) and _COOKED_AUSILIARI & set(tokens_prova):
        nome = _nome_cucinato(tokens_prova)
        if nome:
            return {**base, "intent": "recipe_cooked", "name": nome}

    # Creazione di una ricetta: serve un verbo di "nuova" insieme alla parola
    # "ricetta". Prima della ricerca e degli ingredienti, perché "aggiungi la
    # ricetta carbonara" senza questo ramo finirebbe in lista della spesa come
    # articolo "ricetta carbonara".
    # Una destinazione esplicita vince: "aggiungi la ricetta nel carrello" parla
    # del carrello, non di una ricetta da scrivere. "ingredienti" esclude a sua
    # volta: chi lo dice vuole toccare gli ingredienti di una ricetta esistente,
    # non crearne una nuova chiamata "ingredienti ...".
    tokens_frase = normalized.split()
    if (_RECIPE_WORDS & set(tokens_frase) and _RECIPE_VERBS & set(tokens_frase)
            and not _find_destination(tokens_frase)[2]
            and not ({"ingredienti", "ingrediente"} & set(tokens_frase))):
        # la coda con le dosi è un elenco di ingredienti, non parte del nome:
        # senza separarla, il titolo della ricetta diventava "pasta al forno con
        # 500 grammi di pasta e 300 grammi di pomodoro"
        inizio_ingredienti = _nome_da_ingredienti(tokens_frase)
        nome = _nome_ricetta(tokens_frase, inizio_ingredienti)
        ingredienti = (_ingredienti_da_dettato(tokens_frase[inizio_ingredienti:])
                       if inizio_ingredienti is not None else [])
        return {**base, "intent": "recipe_add", "name": nome, "items": ingredienti}

    # ricerca fra le ricette
    match = re.search(r"\b(cerca|cercami|cercare|mostrami|trova)\b", normalized)
    if match:
        query = normalized[match.end():]
        query = " ".join(t for t in query.split() if t not in _SEARCH_WORDS)
        if query:
            return {**base, "intent": "recipe_search", "query": query}

    tokens = normalized.split()
    quantity, unit, qty_idx = _extract_amount(tokens)
    skip = set(qty_idx)
    dest, dest_idx, explicit, luogo = _find_destination(tokens)
    if dest_idx is not None:
        skip.add(dest_idx)
    # se la destinazione e' il magazzino per via della parola "magazzino", quella
    # parola non fa parte del nome ("il sapone al magazzino" -> "sapone")
    if dest == "storage":
        for i, tok in enumerate(tokens):
            if i not in skip and tok in _DEST_TOKENS and _DEST_TOKENS[tok] == "storage":
                skip.add(i)

    # una frase senza verbo di comando, senza destinazione e senza quantità è
    # rumore di fondo o un fraintendimento del riconoscimento, non un comando:
    # meglio non scrivere niente che scrivere una voce sbagliata in lista
    segnali = bool(_COMMAND_VERBS & set(tokens)) or explicit
    if not segnali and quantity is None and unit is None:
        return base

    name = _clean_name(tokens, skip)
    if not name:
        return base

    # Un ingrediente non si chiama "ricetta": se la parola resta nel nome la
    # frase parlava di ricette e non di spesa ("vorrei una ricetta", "metti la
    # ricetta carbonara"). Meglio non capire che scrivere "ricetta carbonara"
    # in lista: l'utente riprova, l'articolo sbagliato resta li' per sempre.
    if _RECIPE_WORDS & set(name.split()):
        return base

    # l'etto diventa grammi: in dispensa le quantità restano confrontabili
    if unit == "etto":
        unit = "g"
        quantity = (quantity or 0) * 100

    if dest == "storage":
        categoria = _categoria_deducibile(tokens)
        return {
            **base,
            "intent": "storage_add",
            "name": name,
            "quantity": quantity,
            "unit": unit,
            "explicit": explicit,
            "place": luogo,
            "category": categoria,
        }

    intent = {"pantry": "pantry_add", "shopping": "shopping_add"}.get(dest, "shopping_add")
    return {
        **base,
        "intent": intent,
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "explicit": explicit,
    }

# "che" non fa parte del nome di un alimento: "metti il sale, che serve" e'
# "sale" e basta. Si toglie solo quando e' una parola a se'.
_STOPWORDS = _STOPWORDS | {"che"}
