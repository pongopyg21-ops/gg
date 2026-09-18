"""Comandi vocali: dalla frase dettata al comando strutturato.

Il riconoscimento vocale avviene nel browser (Web Speech API), che restituisce
solo testo: qui quel testo diventa un comando per l'app. Tenere la comprensione
sul server permette di verificarla con dei test, senza microfono.

Esempi di frasi riconosciute:

    "aggiungi due chili di farina alla dispensa"  -> dispensa, farina, 2 kg
    "metti il latte nella spesa"                  -> spesa, latte, 1 pz
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
    "allergia": "term", "allergie": "term", "intolleranza": "term",
    "intolleranze": "term", "restrizioni": "term",
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
    """(destinazione, indice, esplicita). Senza indizi vale la spesa."""
    for i, tok in enumerate(tokens):
        dest = _DEST_TOKENS.get(tok)
        if dest:
            return dest, i, True
    return "shopping", None, False


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


def parse(text):
    """Comando strutturato ricavato dalla frase dettata.

    Ritorna un dizionario con `intent` fra:
    `pantry_add`, `shopping_add`, `term_add`, `recipe_search`, `unknown`.
    """
    raw = str(text or "").strip()
    normalized = _norm(raw)
    base = {"intent": "unknown", "text": raw}
    if not normalized:
        return base

    # allergie e intolleranze: un termine per il profilo
    if re.search(r"\b(allergi\w*|intolleran\w*|restrizion\w*)\b", normalized):
        terms = _clean_term(normalized)
        if terms:
            return {**base, "intent": "term_add", "terms": terms}

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
    dest, dest_idx, explicit = _find_destination(tokens)
    if dest_idx is not None:
        skip.add(dest_idx)

    # una frase senza verbo di comando, senza destinazione e senza quantità è
    # rumore di fondo o un fraintendimento del riconoscimento, non un comando:
    # meglio non scrivere niente che scrivere una voce sbagliata in lista
    segnali = bool(_COMMAND_VERBS & set(tokens)) or explicit
    if not segnali and quantity is None and unit is None:
        return base

    name = _clean_name(tokens, skip)
    if not name:
        return base

    # l'etto diventa grammi: in dispensa le quantità restano confrontabili
    if unit == "etto":
        unit = "g"
        quantity = (quantity or 0) * 100

    intent = {"pantry": "pantry_add", "shopping": "shopping_add"}.get(dest, "shopping_add")
    return {
        **base,
        "intent": intent,
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "explicit": explicit,
    }