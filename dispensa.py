"""Cosa cucinare con quello che c'e' gia' in dispensa.

Modulo a parte perche' e' una funzione che non tocca i dati: legge dispensa,
ricette e allergie e restituisce una classifica. Cosi' si prova senza browser e
senza cucinare davvero.

Il criterio e' la **copertura**: quali ingredienti della ricetta sono gia' in
casa. Ordinare per ingredienti coperti sarebbe pero' un premio alle ricette
lunghe: una da dodici ingredienti con sette in dispensa batterebbe una da
quattro con quattro, che invece si puo' fare subito. Il punteggio e' quindi una
frazione, e a parita' vince la spesa piu' corta.

Un ingrediente coperto **in parte** conta mezzo punto, non uno: con 100 g di
farina in casa e 500 g richiesti la ricetta non si fa, ma non e' nemmeno da
comprare tutta. Contarlo intero direbbe che e' pronta quando non lo e'.

Le quantita' si confrontano solo fra unita' convertibili (`units.convert`):
200 g coprono 0,2 kg, ma una confezione non copre un pezzo, e li' non si
indovina — un ingrediente senza scorta si dice mancante.
"""

import datetime

import allergens
import units

# oltre questo numero i nomi nella riga diventano illeggibili: il resto lo dice
# il conteggio, che resta esatto
MAX_NOMI = 5

# Cosa si considera "sta per scadere". Una settimana e' il giro di una spesa:
# oltre, non e' piu' un problema di stasera.
GIORNI_SCADENZA = 7


def _dispensa(db):
    """ingredient_id -> {nome, scorte: [(quantita', unita', scadenza), ...]}.

    Le scorte sono una lista perche' lo stesso ingrediente puo' avere piu' righe
    in unita' diverse (500 g e 1 confezione): vanno sommate solo quelle
    convertibili, e la somma la fa `_coperto`.
    """
    out = {}
    for r in db.execute(
            """SELECT p.ingredient_id, p.quantity, p.unit, p.expires_at, i.name
               FROM pantry p JOIN ingredients i ON i.id = p.ingredient_id"""):
        voce = out.setdefault(r["ingredient_id"], {"nome": r["name"], "scorte": []})
        voce["scorte"].append((r["quantity"], r["unit"], r["expires_at"]))
    return out


def _scade_presto(scorte, oggi):
    """La scorta piu' vicina alla scadenza, se e' entro `GIORNI_SCADENZA`.

    Un ingrediente senza data non scade per questo: non sapere quando scade non
    e' un motivo per metterlo in cima.
    """
    limite = oggi + datetime.timedelta(days=GIORNI_SCADENZA)
    for _, _, scadenza in scorte:
        if not scadenza:
            continue
        try:
            data = datetime.date.fromisoformat(scadenza)
        except ValueError:
            continue
        if data <= limite:
            return scadenza
    return None


def _coperto(quantita, unita, scorte):
    """(coperto, presente): coperto del tutto, oppure solo in parte.

    `presente` distingue «non ne ho» da «ne ho meno del necessario»: sono due
    situazioni diverse per chi deve decidere se comprare.
    """
    totale = 0.0
    presente = False
    for q, u, _ in scorte:
        conv = units.convert(q, u, unita)
        if conv is not None:
            totale += conv
            presente = True
        elif units.normalize(u) == units.normalize(unita):
            # unita' non convertibili (pz, confezione): contano solo se identiche
            totale += q
            presente = True
    if not presente:
        return False, False
    if quantita <= 0:
        return True, True
    return totale >= quantita, True


def suggerimenti(db, restrizioni=(), limite=6, oggi=None):
    """Ricette ordinate per quanto usano la dispensa.

    `restrizioni` sono i termini allergici del profilo: una ricetta che li
    contiene **non** viene suggerita. Marcarne una con un avviso andrebbe bene in
    un elenco da consultare, ma qui l'app dice «cucina questa»: proporre un
    allergene non e' un'informazione, e' un errore.

    `oggi` serve per la scadenza: chi ha scorte in scadenza sale in cima, perche'
    la ricetta che le consuma e' quella da cucinare adesso. Senza, si usa la data
    vera — l'unico posto in cui il modulo la guarda.
    """
    oggi = oggi or datetime.date.today()
    dispensa = _dispensa(db)
    if not dispensa:
        return {"dispensa": 0, "suggerimenti": []}

    per_ricetta = {}
    for r in db.execute(
            """SELECT ri.recipe_id, ri.quantity, ri.unit, ri.ingredient_id, i.name
               FROM recipe_items ri JOIN ingredients i ON i.id = ri.ingredient_id"""):
        per_ricetta.setdefault(r["recipe_id"], []).append(r)

    fuori = []
    for rec in db.execute(
            "SELECT id, name, servings, time_minutes FROM recipes ORDER BY name"):
        suoi = per_ricetta.get(rec["id"]) or []
        if not suoi:
            # senza ingredienti non c'e' niente da consumare: non e' un suggerimento
            continue
        nomi = [i["name"] for i in suoi]
        tags = allergens.tags_for(nomi)
        if allergens.matching_terms(restrizioni, tags, nomi):
            continue

        coperti = parziali = 0
        mancano = []
        scadono = []
        for i in suoi:
            voce = dispensa.get(i["ingredient_id"])
            if voce:
                intero, presente = _coperto(i["quantity"], i["unit"], voce["scorte"])
                if _scade_presto(voce["scorte"], oggi):
                    scadono.append(i["name"])
            else:
                intero, presente = False, False
            if intero:
                coperti += 1
            elif presente:
                parziali += 1
                mancano.append(i["name"])
            else:
                mancano.append(i["name"])
        # una ricetta che non usa niente di quello che c'e' non aiuta a consumarlo
        if not coperti and not parziali:
            continue

        totale = len(suoi)
        mancanti = totale - coperti
        fuori.append({
            "id": rec["id"],
            "name": rec["name"],
            "servings": rec["servings"],
            "time_minutes": rec["time_minutes"],
            "totale": totale,
            "coperti": coperti,
            "parziali": parziali,
            "mancanti": mancanti,
            "pronta": mancanti == 0,
            # frazione, non conteggio: cosi' una ricetta corta e completa batte
            # una lunga e incompleta, che e' quella che si puo' cucinare stasera
            "punteggio": round((coperti + 0.5 * parziali) / totale, 3),
            "mancano": mancano[:MAX_NOMI],
            # quante scorte in scadenza questa ricetta aiuterebbe a consumare
            "scadono": scadono[:MAX_NOMI],
        })

    # In cima chi consuma qualcosa in scadenza: la copertura dice cosa si puo'
    # fare, la scadenza dice cosa conviene fare adesso. A parita' di scadenze
    # consumate, valgono copertura e spesa corta, come prima.
    fuori.sort(key=lambda s: (-len(s["scadono"]), -s["punteggio"], s["mancanti"], s["name"]))
    return {"dispensa": len(dispensa), "suggerimenti": fuori[:limite]}
