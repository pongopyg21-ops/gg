"""Comandi vocali, voce neurale, ascolto e sveglia.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_voce_riconosce_quantita_a_parole_e_in_cifre():
    cmd = voice.parse("aggiungi due chili di farina in dispensa")
    assert cmd["intent"] == "pantry_add"
    assert (cmd["name"], cmd["quantity"], cmd["unit"]) == ("farina", 2.0, "kg")

    cmd = voice.parse("aggiungi 500 grammi di pasta alla spesa")
    assert (cmd["name"], cmd["quantity"], cmd["unit"]) == ("pasta", 500.0, "g")

def test_voce_converte_gli_etti_in_grammi():
    """L'etto non esiste come unità dell'app: 2 etti devono diventare 200 g."""
    for frase in ("due etti di prosciutto in dispensa", "aggiungi 3 etti di ricotta"):
        cmd = voice.parse(frase)
        assert cmd["quantity"] == (200.0 if "due" in frase else 300.0)
        assert cmd["unit"] == "g"

def test_voce_riconosce_le_frazioni():
    assert voice.parse("mezzo litro di latte in dispensa")["quantity"] == 0.5
    assert voice.parse("un chilo e mezzo di patate in dispensa")["quantity"] == 1.5
    assert voice.parse("un quarto di burro in dispensa")["quantity"] == 0.25
    # "un quarto" non deve essere letto come "un" + unità
    assert voice.parse("un quarto di burro in dispensa")["unit"] is None
    assert voice.parse("due litri e un quarto di acqua")["quantity"] == 2.25

def test_voce_numeri_a_parole_composti():
    assert voice.parse("venticinque grammi di lievito")["quantity"] == 25.0
    assert voice.parse("centoventi grammi di ricotta")["quantity"] == 120.0
    assert voice.parse("duecento grammi di zucchero")["quantity"] == 200.0
    assert voice.parse("mille grammi di farina")["quantity"] == 1000.0

def test_voce_destinazione_predefinita_e_lista_della_spesa():
    assert voice.parse("metti il latte nella spesa")["intent"] == "shopping_add"
    # senza indicazioni si finisce in lista, non in dispensa
    assert voice.parse("aggiungi il pane")["intent"] == "shopping_add"
    assert voice.parse("metti il burro in dispensa")["intent"] == "pantry_add"

def test_voce_ripulisce_il_nome_dell_ingrediente():
    casi = {
        "aggiungi due chili di farina alla dispensa": "farina",
        "metti il latte nella spesa": "latte",
        "ci vorrebbero due litri di acqua": "acqua",
        "tre confezioni di passata di pomodoro in dispensa": "passata di pomodoro",
        "aggiungi l'acqua alla spesa": "acqua",
    }
    for frase, atteso in casi.items():
        assert voice.parse(frase)["name"] == atteso, frase

def test_voce_rimozione_non_diventa_un_aggiunta():
    """Il difetto visto dall'utente: "togli il latte dalla dispensa" **aggiungeva**
    il latte in dispensa, con l'articolo chiamato "togli il latte".

    Verificato sull'endpoint vero prima della correzione: rispondeva "Fatto.
    Togli il latte in dispensa, 1 pz." Non e' un fraintendimento innocuo: scrive
    nella dispensa una voce che non esiste e non toglie quel che serviva."""
    cmd = voice.parse("togli il latte dalla dispensa")
    assert cmd["intent"] == "pantry_remove"
    assert cmd["name"] == "latte"

    # senza destinazione si toglie dalla lista: la dispensa si nomina, la lista
    # e' il posto da cui si toglie e basta
    assert voice.parse("togli il latte")["intent"] == "shopping_remove"
    assert voice.parse("rimuovi il pane dalla spesa")["intent"] == "shopping_remove"

def test_voce_consumo_scala_la_dispensa():
    """"ho finito il latte" e "ho usato 300 grammi di farina" non sono aggiunte:
    consumano. Prima non venivano capite affatto oppure finivano in lista."""
    cmd = voice.parse("ho finito il latte")
    assert cmd["intent"] == "pantry_consume" and cmd["name"] == "latte"

    cmd = voice.parse("ho usato 300 grammi di farina")
    assert cmd["intent"] == "pantry_consume"
    assert cmd["name"] == "farina" and cmd["quantity"] == 300.0 and cmd["unit"] == "g"

def test_voce_preso_spunta_la_lista():
    """Non e' una rimozione: la voce resta fra le prese, come spuntarla a mano."""
    cmd = voice.parse("ho preso il pane")
    assert cmd["intent"] == "shopping_check" and cmd["name"] == "pane"
    assert voice.parse("ho comprato il latte")["intent"] == "shopping_check"

def test_voce_la_cottura_resta_la_cottura():
    """Il verbo "ho preparato" e' cottura di una ricetta, non aggiunta a dispensa:
    la nuova lettura non deve rubargli la frase."""
    cmd = voice.parse("ho cucinato la carbonara")
    assert cmd["intent"] == "recipe_cooked" and cmd["name"] == "carbonara"

def test_voce_togliere_dalla_dispensa_endpoint(client):
    """Dal server: la voce sparisce davvero, e le altre restano."""
    client.post("/api/pantry", json={"name": "Latte", "quantity": 2, "unit": "l"})
    client.post("/api/pantry", json={"name": "Pane", "quantity": 1, "unit": "pz"})
    r = client.post("/api/voice", json={"text": "togli il latte dalla dispensa"})
    assert r.status_code == 200
    assert "Latte" in r.get_json()["message"]
    nomi = [v["name"] for v in client.get("/api/pantry").get_json()]
    assert "Latte" not in nomi
    assert "Pane" in nomi, "le altre voci della dispensa non si toccano"

def test_voce_consumo_scala_la_quantita_endpoint(client):
    """Con una quantita' la voce resta, diminuita; se arriva a zero sparisce."""
    client.post("/api/pantry", json={"name": "Farina", "quantity": 1000, "unit": "g"})
    r = client.post("/api/voice", json={"text": "ho usato 300 grammi di farina"})
    assert r.status_code == 200
    riga = [v for v in client.get("/api/pantry").get_json() if v["name"] == "Farina"][0]
    assert riga["quantity"] == 700

    client.post("/api/voice", json={"text": "ho finito la farina"})
    assert not [v for v in client.get("/api/pantry").get_json() if v["name"] == "Farina"]

def test_voce_quello_che_non_capisce_non_scrive_niente(client):
    """Una frase senza un alimento non deve inventare un articolo: meglio non
    capire che sporcare la dispensa."""
    client.post("/api/voice", json={"text": "prepara la carbonara"})
    dispensa = client.get("/api/pantry").get_json()
    assert dispensa == [], f"la dispensa doveva restare vuota, invece: {dispensa}"

def test_voce_domanda_su_cosa_comprare_non_e_un_ordine(client):
    """"cosa devo comprare" finiva in lista come articolo "cosa": rispondeva
    "Fatto. Cosa in lista, 1 pz." — una domanda **eseguita** come ordine. Ora e'
    una domanda, e la risposta e' quello che manca."""
    cmd = voice.parse("cosa devo comprare")
    assert cmd["intent"] == "domanda" and cmd["area"] == "shopping"

    # il luogo vince: "cosa manca in dispensa" parla della dispensa
    assert voice.parse("cosa manca in dispensa")["area"] == "pantry"
    # un alimento vince sulla lista: "quanto sale serve" cerca il sale
    cmd = voice.parse("quanto sale serve")
    assert cmd["intent"] == "domanda" and cmd["area"] == "pantry" and cmd["query"] == "sale"

    r = client.post("/api/voice", json={"text": "cosa devo comprare"})
    assert r.status_code == 200
    assert client.get("/api/shopping").get_json() == [], "nessun articolo 'cosa' in lista"

def test_voce_domanda_sulla_lista_risponde_con_le_voci(client):
    """La domanda sulla lista nominava una tabella inesistente (`FROM shopping`) e
    rispondeva 500. Ora elenca le voci vere."""
    client.post("/api/shopping", json={"name": "Latte", "quantity": 2, "unit": "l"})
    r = client.post("/api/voice", json={"text": "cosa devo comprare"})
    assert r.status_code == 200
    assert "Latte" in r.get_json()["message"]

    r = client.post("/api/voice", json={"text": "cosa c'è in lista"})
    assert r.status_code == 200
    assert "Latte" in r.get_json()["message"]

def test_voce_registra_allergie_e_intolleranze():
    cmd = voice.parse("sono allergico al nichel")
    assert cmd["intent"] == "term_add"
    assert cmd["terms"] == ["nichel"]

    # più termini separati da "e", con l'articolo da togliere
    cmd = voice.parse("sono intollerante al lattosio e al fruttosio")
    assert cmd["terms"] == ["lattosio", "fruttosio"]

    # "frutta a guscio" è un'etichetta unica e non va spezzata
    cmd = voice.parse("sono allergico alla frutta a guscio")
    assert cmd["terms"] == ["frutta a guscio"]

def test_voce_ricerca_ricette():
    cmd = voice.parse("cerca la carbonara")
    assert cmd["intent"] == "recipe_search"
    assert cmd["query"] == "carbonara"
    assert voice.parse("cercami ricette con le melanzane")["query"] == "melanzane"

def test_voce_crea_ricetta_dettata():
    """Dettare una ricetta nuova: si apre il modulo col nome, non si crea a vuoto."""
    casi = {
        "crea la ricetta carbonara": "carbonara",
        "aggiungi la ricetta carbonara": "carbonara",
        "crea una ricetta chiamata pasta al forno": "pasta al forno",
        "nuova ricetta polpette della nonna": "polpette della nonna",
        "salva la ricetta risotto ai funghi": "risotto ai funghi",
        "prepara una ricetta per la carbonara": "carbonara",
        "vorrei aggiungere una ricetta di lasagne": "lasagne",
    }
    for frase, atteso in casi.items():
        cmd = voice.parse(frase)
        assert cmd["intent"] == "recipe_add", frase
        assert cmd["name"] == atteso, frase

def test_voce_senza_nome_chiede_il_modulo_vuoto():
    """"aggiungi una ricetta" non ha un nome: il modulo si apre comunque, vuoto."""
    cmd = voice.parse("aggiungi una ricetta")
    assert cmd["intent"] == "recipe_add"
    assert cmd["name"] == ""

def test_voce_crea_ricetta_con_i_verbi_di_tutti_i_giorni():
    """Nessuno dice "crea la ricetta": si dice "fammi una ricetta di lasagne".

    Con i soli verbi "crea/aggiungi/salva" la frase piu' naturale di tutte
    restava `unknown`, e chi la diceva riceveva "non ho capito" per una cosa
    chiarissima. "fai" e "fammi" sono verbi di creazione come gli altri.
    """
    casi = {
        "fai una ricetta di lasagne": "lasagne",
        "fammi una ricetta di carbonara": "carbonara",
        "mi fai una ricetta di lasagne": "lasagne",
        "fai la ricetta carbonara": "carbonara",
        "fammi la ricetta carbonara": "carbonara",
        "fare una ricetta di pizza": "pizza",
    }
    for frase, atteso in casi.items():
        cmd = voice.parse(frase)
        assert cmd["intent"] == "recipe_add", frase
        assert cmd["name"] == atteso, frase

def test_voce_fammi_vedere_non_crea_una_ricetta():
    """"fammi" ora crea ricette, quindi "fammi **vedere**" deve restare fuori.

    Chiedere di vedere una ricetta e vedersi aprire il modulo di una ricetta
    nuova e' l'errore opposto a quello appena corretto, e altrettanto fastidioso:
    il verbo di creazione c'e', ma il senso e' un altro.
    """
    for frase in ("fammi vedere la ricetta carbonara",
                  "voglio vedere la ricetta carbonara",
                  "mi fai leggere la ricetta carbonara"):
        assert voice.parse(frase)["intent"] != "recipe_add", frase

def test_voce_fammi_la_spesa_non_scrive_fammi_in_lista():
    """Una frase di comando senza alimento non deve produrre un alimento.

    "fammi la spesa" non dice *cosa* comprare: senza questa guardia il verbo
    finiva in lista come articolo chiamato "fammi", ed era lo stesso guasto di
    "che cosa c'e' in dispensa" per un'altra strada. Una voce sbagliata in lista
    resta li' per sempre, quindi meglio non capire.
    """
    for frase in ("fammi la spesa", "fai la spesa", "fammi la lista della spesa",
                  "fai il punto della spesa", "fammi vedere la spesa",
                  "fammi la dispensa", "fai il magazzino"):
        cmd = voice.parse(frase)
        assert cmd["intent"] == "unknown", (frase, cmd)

def test_una_frase_senza_alimento_non_tocca_la_lista(client):
    """Il comportamento vero: dopo "fammi la spesa" la lista resta vuota.

    Provarlo con `voice.parse` dice che la frase non viene capita; provarlo qui
    dice che il server non ha scritto niente. Sono due cose diverse: la prima
    puo' essere vera mentre la seconda e' falsa se un ramo a valle indovina.
    """
    lista_prima = client.get("/api/shopping").get_json()
    for frase in ("fammi la spesa", "fai la spesa", "fammi la lista della spesa"):
        assert client.post("/api/voice", json={"text": frase}).status_code == 422
    assert client.get("/api/shopping").get_json() == lista_prima

def test_voce_la_parola_della_destinazione_non_e_un_alimento():
    """La destinazione dice *dove*, non *cosa*: non fa parte del nome.

    "il sapone al magazzino" -> "sapone" (non "sapone magazzino"), e in
    "aggiungi il latte alla spesa" l'articolo e' "latte", non "latte spesa".
    """
    assert voice.parse("metti il sapone al magazzino")["name"] == "sapone"
    assert voice.parse("aggiungi il latte alla spesa")["name"] == "latte"
    assert voice.parse("metti il latte in lista")["name"] == "latte"

def test_voce_ricetta_non_finisce_nella_spesa():
    """Senza il ramo `recipe_add`, "aggiungi la ricetta carbonara" diventava una
    voce di lista della spesa chiamata "ricetta carbonara"."""
    cmd = voice.parse("aggiungi la ricetta carbonara")
    assert cmd["intent"] != "shopping_add"
    assert cmd["intent"] != "pantry_add"

def test_voce_ricetta_non_tocca_gli_altri_comandi():
    """Le frasi di ingredienti, allergie e ricerca restano quelle di prima."""
    assert voice.parse("aggiungi il pane")["intent"] == "shopping_add"
    assert voice.parse("metti il burro in dispensa")["intent"] == "pantry_add"
    assert voice.parse("sono allergico al nichel")["intent"] == "term_add"
    assert voice.parse("cerca la carbonara")["intent"] == "recipe_search"
    assert voice.parse("tre confezioni di passata di pomodoro in dispensa")["name"] == "passata di pomodoro"

def test_voce_ricetta_ambigua_non_diventa_un_articolo():
    """Le frasi in cui "ricetta" è l'oggetto del discorso ma non una ricetta da
    scrivere non devono produrre una voce di lista chiamata "ricetta ...".

    Sono i casi in cui la frase parla di una ricetta senza chiedere di crearne
    una: una destinazione esplicita ("nel carrello"), un verbo debole ("vorrei"),
    o gli ingredienti di una ricetta che esiste già."""
    for frase in ("vorrei una ricetta",
                  "voglio una ricetta",
                  "metti la ricetta carbonara",
                  "mi serve una ricetta per la cena",
                  "aggiungi la ricetta nel carrello",
                  "metti la ricetta nel carrello",
                  "aggiungi gli ingredienti della ricetta carbonara"):
        cmd = voice.parse(frase)
        assert cmd["intent"] != "shopping_add", frase
        assert cmd["intent"] != "pantry_add", frase
        assert cmd["intent"] != "recipe_add", frase

def test_voce_ricetta_nel_carrello_resta_una_destinazione():
    """Una destinazione esplicita vince sulla parola "ricetta"."""
    assert voice.parse("aggiungi la ricetta nel carrello")["intent"] == "unknown"

def test_voce_ricetta_legge_gli_ingredienti_dettati():
    """Chi detta una ricetta dice anche cosa ci va, e le dosi non devono finire
    nel nome.

    Prima finivano tutte nel titolo: "crea la ricetta pasta al forno con 500
    grammi di pasta e 300 grammi di pomodoro" diventava una ricetta chiamata
    così, dosi comprese. Il modulo si apriva con quel titolo assurdo e la voce
    sembrava aver capito, mentre l'unica cosa utile — gli ingredienti — andava
    persa."""
    cmd = voice.parse("crea la ricetta pasta al forno con 500 grammi di pasta e 300 grammi di pomodoro")
    assert cmd["intent"] == "recipe_add"
    assert cmd["name"] == "pasta al forno"
    assert cmd["items"] == [{"name": "pasta", "quantity": 500, "unit": "g"},
                            {"name": "pomodoro", "quantity": 300, "unit": "g"}]

def test_voce_ricetta_ingredienti_contati_senza_unita():
    """"4 uova" è una dose anche senza unità di misura."""
    cmd = voice.parse("crea la ricetta carbonara con 4 uova")
    assert cmd["name"] == "carbonara"
    assert cmd["items"] == [{"name": "uova", "quantity": 4, "unit": None}]

def test_voce_ricetta_virgola_dettata_separa_gli_ingredienti():
    """Le virgole non arrivano dal riconoscimento vocale: "guanciale, 4 uova"
    è "guanciale 4 uova", e il numero apre un ingrediente nuovo."""
    cmd = voice.parse("nuova ricetta carbonara con 200 grammi di guanciale, 4 uova e 100 grammi di pecorino")
    assert cmd["name"] == "carbonara"
    assert [i["name"] for i in cmd["items"]] == ["guanciale", "uova", "pecorino"]
    assert [i["quantity"] for i in cmd["items"]] == [200, 4, 100]

def test_voce_ricetta_senza_dosi_resta_solo_il_nome():
    """Un nome con un numero dentro non è un elenco di ingredienti.

    "torta 7 vasetti" è il nome di una torta: senza l'unità di misura o il "con",
    un numero non basta a dire che comincia l'elenco, altrimenti la ricetta si
    chiamerebbe "torta"."""
    cmd = voice.parse("crea la ricetta torta 7 vasetti")
    assert cmd["name"] == "torta 7 vasetti"
    assert cmd["items"] == []

def test_voce_ricetta_gli_ingredienti_non_sono_un_nome_di_ricetta():
    """Gli ingredienti dettati restano fuori dal nome, ma senza dosi non c'è
    niente da separare: il nome resta quello che si è detto."""
    cmd = voice.parse("crea la ricetta pasta al forno con la pasta e il pomodoro")
    assert cmd["name"] == "pasta al forno con la pasta e il pomodoro"
    assert cmd["items"] == []

def test_voce_endpoint_ricetta_riporta_gli_ingredienti(client):
    """Il modulo deve poterli precompilare: la risposta li porta con sé."""
    r = client.post("/api/voice",
                    json={"text": "crea la ricetta pasta al forno con 500 grammi di pasta e 300 grammi di pomodoro"})
    d = r.get_json()
    assert d["open_recipe_form"] is True
    assert d["name"] == "pasta al forno"
    assert d["items"] == [{"name": "pasta", "quantity": 500, "unit": "g"},
                          {"name": "pomodoro", "quantity": 300, "unit": "g"}]
    # il messaggio dice che gli ingredienti ci sono: altrimenti sembra che la
    # voce abbia aperto un modulo vuoto
    assert "2" in d["message"]

def test_voce_endpoint_crea_ricetta_apre_il_modulo(client):
    r = client.post("/api/voice", json={"text": "crea la ricetta pasta al forno"})
    assert r.status_code == 200
    dati = r.get_json()
    assert dati["intent"] == "recipe_add"
    assert dati["open_recipe_form"] is True
    assert dati["name"] == "pasta al forno"
    # non si crea nulla da soli: il modulo lo compila l'utente
    assert client.get("/api/recipes").get_json() == []

def test_voce_endpoint_ricetta_senza_nome(client):
    r = client.post("/api/voice", json={"text": "aggiungi una ricetta"})
    assert r.status_code == 200
    assert r.get_json()["open_recipe_form"] is True

def test_voce_ricetta_cucinata_riconosce_il_nome():
    """"ho cucinato/preparato X" e' una ricetta consumata, non una da creare."""
    casi = {
        "ho cucinato pasta al sugo": "pasta al sugo",
        "ho preparato pasta al sugo": "pasta al sugo",
        "ho cucinato la pasta al sugo": "pasta al sugo",
        "ho cotto le lasagne": "lasagne",
        "avevo preparato il risotto ai funghi": "risotto ai funghi",
        "ho cucinato pasta al sugo oggi": "pasta al sugo",
        "ho preparato una ricetta per la carbonara": "carbonara",
    }
    for frase, atteso in casi.items():
        cmd = voice.parse(frase)
        assert cmd["intent"] == "recipe_cooked", frase
        assert cmd["name"] == atteso, frase

def test_voce_cucinato_non_e_una_ricetta_da_creare():
    """Il ramo cucinato sta prima di `recipe_add`: "ho preparato una ricetta"
    aprirebbe altrimenti il modulo di una ricetta nuova."""
    assert voice.parse("ho preparato una ricetta per la carbonara")["intent"] != "recipe_add"
    # l'imperativo resta una creazione: e' il participio passato a cambiare tutto
    assert voice.parse("prepara una ricetta per la carbonara")["intent"] == "recipe_add"
    assert voice.parse("prepara la ricetta carbonara")["intent"] == "recipe_add"

def test_voce_cucinato_non_riconosce_frasi_generiche():
    """Senza indicare cosa si e' cucinato, o con un participio aggettivale, non
    si scala niente: e' un comando che tocca la dispensa, va riconosciuto bene."""
    for frase in ("ho preparato la cena", "ho mangiato la pasta",
                  "la pasta cucinata ieri", "ho cotto"):
        assert voice.parse(frase)["intent"] != "recipe_cooked", frase

def test_voce_endpoint_cucinato_scala_la_dispensa(client):
    """Il caso della richiesta: pasta e sugo in dispensa, si cucina "pasta al
    sugo" e le quantita' degli ingredienti si sottraggono."""
    _ricetta_con_ingredienti(client, "pasta al sugo",
                             [("pasta", 500, "g"), ("sugo", 300, "g")])
    client.post("/api/pantry", json={"name": "pasta", "quantity": 1, "unit": "kg"})
    client.post("/api/pantry", json={"name": "sugo", "quantity": 500, "unit": "g"})

    r = client.post("/api/voice", json={"text": "ho cucinato pasta al sugo"})
    assert r.status_code == 200
    dati = r.get_json()
    assert dati["intent"] == "recipe_cooked"
    assert dati["scalati"] == ["pasta", "sugo"]

    dispensa = {v["name"]: (v["quantity"], v["unit"]) for v in client.get("/api/pantry").get_json()}
    # 1 kg - 500 g = 500 g, e la riga resta in chili: e' l'unita' scelta dall'utente
    assert dispensa["pasta"] == (0.5, "kg")
    assert dispensa["sugo"] == (200, "g")

def test_voce_endpoint_preparato_scala_la_dispensa_come_cucinato(client):
    """"ho preparato X" deve fare **lo stesso** di "ho cucinato X".

    Sono due modi di dire la stessa cosa, e la frase dell'utente li usa
    entrambi: se il percorso dell'uno si rompe, l'altro continuerebbe a
    funzionare e il guasto passerebbe inosservato.
    """
    _ricetta_con_ingredienti(client, "risotto ai funghi", [("riso", 300, "g")])
    client.post("/api/pantry", json={"name": "riso", "quantity": 1, "unit": "kg"})

    r = client.post("/api/voice", json={"text": "ho preparato il risotto ai funghi"})
    assert r.status_code == 200
    assert r.get_json()["intent"] == "recipe_cooked"
    assert r.get_json()["scalati"] == ["riso"]
    assert client.get("/api/pantry").get_json()[0]["quantity"] == pytest.approx(0.7)

def test_voce_endpoint_cucinato_svuota_la_riga_a_zero(client):
    """Una giacenza che arriva a zero si toglie: una riga a zero non e' una scorta."""
    _ricetta_con_ingredienti(client, "minestrone", [("carote", 2, "pz")])
    client.post("/api/pantry", json={"name": "carote", "quantity": 2, "unit": "pz"})

    client.post("/api/voice", json={"text": "ho cucinato il minestrone"})
    assert client.get("/api/pantry").get_json() == []

def test_voce_endpoint_cucinato_non_bastava(client):
    """Se in dispensa non basta, si dice: dire "fatto" sarebbe una bugia."""
    _ricetta_con_ingredienti(client, "torta", [("farina", 500, "g"), ("zucchero", 200, "g")])
    client.post("/api/pantry", json={"name": "farina", "quantity": 100, "unit": "g"})

    dati = client.post("/api/voice", json={"text": "ho cucinato la torta"}).get_json()
    assert "farina" in dati["mancanti"]
    assert "farina" not in dati["scalati"]
    # la farina c'era ma non bastava: si scala quello che c'e', non si va sotto zero
    dispensa = {v["name"]: v["quantity"] for v in client.get("/api/pantry").get_json()}
    assert "farina" not in dispensa

def test_voce_endpoint_cucinato_unita_incompatibili_non_si_toccano(client):
    """Grammi e pezzi non si convertono: la giacenza resta, l'ingrediente manca."""
    _ricetta_con_ingredienti(client, "uova sode", [("uova", 4, "pz")])
    client.post("/api/pantry", json={"name": "uova", "quantity": 300, "unit": "g"})

    dati = client.post("/api/voice", json={"text": "ho cucinato uova sode"}).get_json()
    assert dati["scalati"] == []
    assert dati["mancanti"] == ["uova"]
    dispensa = {v["name"]: v["quantity"] for v in client.get("/api/pantry").get_json()}
    assert dispensa["uova"] == 300

def test_voce_endpoint_cucinato_ricetta_inesistente(client):
    """Una ricetta che non c'e' non deve toccare la dispensa."""
    client.post("/api/pantry", json={"name": "farina", "quantity": 1, "unit": "kg"})
    r = client.post("/api/voice", json={"text": "ho cucinato pasta al sugo"})
    assert r.status_code == 200
    assert r.get_json()["intent"] == "recipe_cooked"
    assert client.get("/api/pantry").get_json()[0]["quantity"] == 1

def test_voce_endpoint_cucinato_nome_ambiguo_chiede(client):
    """Due ricette che somigliano: si chiede il nome per intero invece di
    scegliere a caso e scalare la dispensa sbagliata."""
    _ricetta_con_ingredienti(client, "pasta al sugo", [("pasta", 500, "g")])
    _ricetta_con_ingredienti(client, "pasta al sugo della nonna", [("pasta", 500, "g")])
    client.post("/api/pantry", json={"name": "pasta", "quantity": 2, "unit": "kg"})

    dati = client.post("/api/voice", json={"text": "ho cucinato pasta al sugo"}).get_json()
    # il nome esatto esiste: vince, e la dispensa si scala
    assert dati["scalati"] == ["pasta"]

    dati = client.post("/api/voice", json={"text": "ho cucinato pasta"}).get_json()
    assert "Dimmi il nome per intero" in dati["message"]
    assert "scalati" not in dati

def test_voce_endpoint_cucinato_rimette_in_lista_quello_consumato(client):
    """Quello che si e' consumato torna da comprare: la lista segue la dispensa."""
    rid = _ricetta_con_ingredienti(client, "pasta al sugo", [("pasta", 500, "g")])
    # la scorta copre esattamente il fabbisogno del piano: la lista e' vuota
    client.post("/api/pantry", json={"name": "pasta", "quantity": 500, "unit": "g"})
    client.post("/api/plan", json={"date": date.today().isoformat(), "meal": "cena", "recipe_id": rid})
    assert {v["name"] for v in client.get("/api/shopping").get_json()} == set()

    client.post("/api/voice", json={"text": "ho cucinato pasta al sugo"})
    # dopo averla consumata la scorta non copre piu' il fabbisogno: torna in lista
    assert {v["name"] for v in client.get("/api/shopping").get_json()} == {"pasta"}

def test_voce_frase_non_compresa():
    assert voice.parse("")["intent"] == "unknown"
    assert voice.parse("   ")["intent"] == "unknown"
    # rumore di fondo o fraintendimento: non deve finire in lista come prodotto
    for frase in ("bla bla", "ehm", "oggi piove forte", "ciao come stai"):
        assert voice.parse(frase)["intent"] == "unknown", frase
    # senza verbo ma con quantità o destinazione resta un comando valido
    assert voice.parse("due chili di farina")["intent"] == "shopping_add"
    assert voice.parse("il latte in dispensa")["intent"] == "pantry_add"

def test_voce_endpoint_aggiunge_in_dispensa(client):
    r = client.post("/api/voice", json={"text": "aggiungi due chili di farina in dispensa"})
    assert r.status_code == 200
    assert "farina" in r.get_json()["message"].lower()

    righe = client.get("/api/pantry").get_json()
    assert len(righe) == 1
    assert righe[0]["name"] == "farina"
    assert righe[0]["quantity"] == 2 and righe[0]["unit"] == "kg"

def test_voce_endpoint_aggiunge_alla_spesa(client):
    r = client.post("/api/voice", json={"text": "metti mezzo litro di latte nella spesa"})
    assert r.status_code == 200
    voci = client.get("/api/shopping").get_json()
    assert [v["name"] for v in voci] == ["latte"]
    assert voci[0]["quantity"] == 0.5 and voci[0]["unit"] == "l"

    # una seconda dettatura si somma, come la generazione della lista
    client.post("/api/voice", json={"text": "aggiungi 500 millilitri di latte alla spesa"})
    voci = client.get("/api/shopping").get_json()
    assert len(voci) == 1
    assert voci[0]["quantity"] == 1 and voci[0]["unit"] == "l"

def test_voce_magazzino_non_e_dispensa_ne_spesa():
    """Il magazzino è una terza destinazione: sapone e detersivo non sono cibo."""
    cmd = voice.parse("aggiungi il sapone al magazzino")
    assert cmd["intent"] == "storage_add"
    assert cmd["name"] == "sapone"

    cmd = voice.parse("metti due rotoli di carta igienica in magazzino")
    assert cmd["intent"] == "storage_add"
    assert cmd["name"] == "rotoli di carta igienica" and cmd["quantity"] == 2.0

    # la destinazione esplicita vince sulla parola dell'oggetto: il sapone
    # messo in dispensa resta in dispensa
    assert voice.parse("aggiungi il sapone in dispensa")["intent"] == "pantry_add"
    # e un prodotto da mangiare senza indizi resta in lista
    assert voice.parse("aggiungi il latte")["intent"] == "shopping_add"

def test_voce_magazzino_riconosce_il_luogo():
    """Il magazzino si dice anche con il posto: "in garage", "in cantina"."""
    cmd = voice.parse("metti il detersivo in cantina")
    assert cmd["intent"] == "storage_add"
    assert (cmd["name"], cmd["place"]) == ("detersivo", "Cantina")

    cmd = voice.parse("aggiungi una scatola di viti in garage")
    assert cmd["intent"] == "storage_add"
    assert (cmd["name"], cmd["place"]) == ("scatola di viti", "Garage")

    # un luogo senza destinazione esplicita vale comunque
    assert voice.parse("metti il trapano in soffitta")["intent"] == "storage_add"

def test_voce_magazzino_deduce_la_categoria():
    """Categoria e luogo sono un di più: se non si capiscono restano i predefiniti."""
    assert voice.parse("aggiungi il detersivo al magazzino")["category"] == "Pulizia casa"
    assert voice.parse("aggiungi il sapone al magazzino")["category"] == "Igiene personale"
    assert voice.parse("aggiungi il dentifricio")["category"] == "Igiene personale"
    assert voice.parse("aggiungi una scatola di viti in garage")["category"] == "Ferramenta"
    assert voice.parse("aggiungi delle lampadine in cantina")["category"] == "Elettricita'"
    # senza indizi la categoria resta vuota e decide il server
    assert voice.parse("aggiungi il coso al magazzino")["category"] is None

def test_voce_magazzino_non_ruba_le_parole_al_nome():
    """La parola "magazzino" non deve finire nel nome della cosa."""
    casi = {
        "aggiungi il sapone al magazzino": "sapone",
        "metti il rotolone in magazzino": "rotolone",
        "aggiungi il detersivo alle scorte": "detersivo",
    }
    for frase, atteso in casi.items():
        cmd = voice.parse(frase)
        assert cmd["intent"] == "storage_add", frase
        assert cmd["name"] == atteso, frase

def test_voce_endpoint_aggiunge_al_magazzino(client):
    r = client.post("/api/voice", json={"text": "aggiungi il sapone al magazzino"})
    assert r.status_code == 200
    assert r.get_json()["reload"] == ["magazzino"]

    voci = client.get("/api/storage").get_json()
    assert len(voci) == 1
    assert voci[0]["name"] == "sapone"
    assert voci[0]["category"] == "Igiene personale"
    assert voci[0]["quantity"] == 1

    # niente di tutto questo deve finire in dispensa o in lista
    assert client.get("/api/pantry").get_json() == []
    assert client.get("/api/shopping").get_json() == []

    # una seconda dettatura dello stesso oggetto accoda alla stessa voce
    client.post("/api/voice", json={"text": "aggiungi il sapone al magazzino"})
    voci = client.get("/api/storage").get_json()
    assert len(voci) == 1 and voci[0]["quantity"] == 2

    # lo stesso nome in un luogo diverso e' una voce a parte
    client.post("/api/voice", json={"text": "metti il sapone in garage"})
    voci = client.get("/api/storage").get_json()
    assert len(voci) == 2
    assert {v["place"] for v in voci} == {"Ripostiglio", "Garage"}

def test_voce_endpoint_aggiunge_al_profilo(client):
    r = client.post("/api/voice", json={"text": "sono allergico al nichel e al fruttosio"})
    assert r.status_code == 200
    assert "nichel" in r.get_json()["message"]

    profilo = client.get("/api/profile").get_json()
    assert profilo["restriction_list"] == ["nichel", "fruttosio"]

    # ripetere lo stesso termine non lo duplica
    client.post("/api/voice", json={"text": "sono allergico al nichel"})
    assert client.get("/api/profile").get_json()["restriction_list"] == ["nichel", "fruttosio"]

def test_voce_endpoint_ricerca_ricette(client):
    r = client.post("/api/voice", json={"text": "cerca la carbonara"})
    assert r.status_code == 200
    assert r.get_json()["query"] == "carbonara"

def test_voce_endpoint_frase_non_compresa(client):
    r = client.post("/api/voice", json={"text": ""})
    assert r.status_code == 422
    assert "capito" in r.get_json()["message"]

def test_il_segreto_si_scrive_in_un_file_di_testo(tmp_path, monkeypatch):
    """`chiave: valore` e `area: valore`: due righe, niente sintassi."""
    _con_segreto(tmp_path, monkeypatch, "chiave: ChiaveDiProva123456\narea: italynorth\n")

    assert voce_cloud.chiave() == "ChiaveDiProva123456"
    assert voce_cloud.regione() == "italynorth"
    assert voce_cloud.configurato()

def test_il_segreto_accetta_le_etichette_che_vengono_naturali(tmp_path, monkeypatch):
    """Chi scrive il file non deve sapere i nomi delle variabili."""
    _con_segreto(tmp_path, monkeypatch, "Chiave: ChiaveDiProva123456\nRegione: italynorth\n")

    assert voce_cloud.chiave() == "ChiaveDiProva123456"
    assert voce_cloud.regione() == "italynorth"

def test_il_segreto_funziona_anche_con_i_due_valori_nudi(tmp_path, monkeypatch):
    """Il file piu' semplice possibile: due righe e basta, prima la chiave.
    L'area e' una parola minuscola, la chiave no: la forma dice cos'e' ciascuna."""
    _con_segreto(tmp_path, monkeypatch, "AbCdEf1234567890xyz\nitalynorth\n")

    assert voce_cloud.chiave() == "AbCdEf1234567890xyz"
    assert voce_cloud.regione() == "italynorth"

def test_il_segreto_nudo_riconosce_l_area_dopo_la_chiave_e_viceversa(tmp_path, monkeypatch):
    """L'ordine non deve contare: chi scrive il file puo' mettere prima l'area."""
    _con_segreto(tmp_path, monkeypatch, "italynorth\nAbCdEf1234567890xyz\n")

    assert voce_cloud.chiave() == "AbCdEf1234567890xyz"
    assert voce_cloud.regione() == "italynorth"

def test_una_riga_di_testo_libero_non_diventa_la_chiave(tmp_path, monkeypatch):
    """Il file puo' contenere una spiegazione scritta a mano: le righe con spazi
    non sono ne' chiave ne' area, e non devono finire nell'ambiente."""
    _con_segreto(tmp_path, monkeypatch,
                 "Questa e' la chiave della voce, non copiarla in giro\n"
                 "chiave: ChiaveDiProva123456\narea: italynorth\n")

    assert voce_cloud.chiave() == "ChiaveDiProva123456"
    assert voce_cloud.regione() == "italynorth"

def test_il_file_senza_estensione_funziona_come_il_txt(tmp_path, monkeypatch):
    """Si possa chiamare `segreto.txt` o solo `segreto`: e' lo stesso."""
    _con_segreto(tmp_path, monkeypatch,
                 "chiave: ChiaveDiProva123456\narea: italynorth\n", nome_file="segreto")

    assert voce_cloud.chiave() == "ChiaveDiProva123456"

def test_l_ambiente_vince_anche_sul_file_di_testo(tmp_path, monkeypatch):
    """Chi esporta la chiave a mano comanda, come per `segreto.sh`."""
    _con_segreto(tmp_path, monkeypatch, "chiave: DalFile\narea: italynorth\n")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "DallAmbiente")

    assert voce_cloud.chiave() == "DallAmbiente"

def test_il_file_di_esempio_non_contiene_una_chiave_vera():
    """Il modello sta su GitHub: se ci finisse una chiave vera sarebbe pubblica.
    Deve contenere solo il segnaposto, e il file vero deve restare escluso."""
    modello = open("segreto.esempio.txt", encoding="utf-8").read()
    assert "incolla-qui-la-chiave" in modello

    import subprocess
    fuori = subprocess.run(["git", "check-ignore", "-q", "segreto.txt"],
                           cwd=voce_cloud.BASE_DIR, capture_output=True).returncode == 0
    dentro = subprocess.run(["git", "check-ignore", "-q", "segreto.esempio.txt"],
                            cwd=voce_cloud.BASE_DIR, capture_output=True).returncode == 0
    assert fuori, "segreto.txt (la chiave vera) deve essere escluso da git"
    assert not dentro, "il modello deve essere versionato"

def test_il_wav_per_il_server_ha_intestazione_e_campioni_giusti(client):
    """Il servizio di ascolto legge **solo** WAV PCM 16 kHz mono: un webm del
    browser verrebbe rifiutato con un 400 che sembra un guasto.

    Si esegue la funzione vera con node e si legge l'intestazione byte per byte:
    un test sulle stringhe non accorgerebbe di un byte scritto male."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function wavDaCampioni"):js.index("\n}\n", js.index("function wavDaCampioni")) + 3]
    prova = blocco + """
// un'onda semplice: positiva e negativa a campioni alterni
const campioni = new Float32Array(320);
for (let i = 0; i < campioni.length; i++) campioni[i] = (i % 2 === 0) ? 0.25 : -0.25;
const blob = wavDaCampioni(campioni, 16000);
blob.arrayBuffer().then((buf) => {
  const v = new DataView(buf);
  const str = (p, n) => { let s = ''; for (let i = 0; i < n; i++) s += String.fromCharCode(v.getUint8(p + i)); return s; };
  console.log(JSON.stringify({
    riff: str(0, 4), wave: str(8, 4), fmt: str(12, 4), data: str(36, 4),
    formato: v.getUint16(20, true), canali: v.getUint16(22, true),
    frequenza: v.getUint32(24, true), bit: v.getUint16(34, true),
    byteDati: v.getUint32(40, true), totale: buf.byteLength,
    primoCampione: v.getInt16(44, true), secondoCampione: v.getInt16(46, true),
  }));
});
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    d = json.loads(esito.stdout)
    assert d["riff"] == "RIFF" and d["wave"] == "WAVE"
    assert d["fmt"] == "fmt " and d["data"] == "data"
    assert d["formato"] == 1          # PCM, non compresso
    assert d["canali"] == 1           # mono
    assert d["frequenza"] == 16000    # quello che chiede il servizio
    assert d["bit"] == 16
    assert d["byteDati"] == 320 * 2   # due byte per campione
    assert d["totale"] == 44 + 320 * 2
    # 0,25 e non 0,5: il mezzo esatto si arrotonda in modo diverso fra JS e
    # Python, e qui non e' quello che si vuole provare
    assert d["primoCampione"] == round(0.25 * 32767)
    assert d["secondoCampione"] == round(-0.25 * 32767)

def test_il_campione_fuori_scala_non_avvolge_di_segno(client):
    """Un valore oltre 1 farebbe avvolgere il numero: 1,5 non è "un po' più
    forte", è un valore negativo. Si taglia al limite."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function wavDaCampioni"):js.index("\n}\n", js.index("function wavDaCampioni")) + 3]
    prova = blocco + """
const campioni = new Float32Array([1.8, -1.9, 0]);
wavDaCampioni(campioni, 16000).arrayBuffer().then((buf) => {
  const v = new DataView(buf);
  console.log([v.getInt16(44, true), v.getInt16(46, true), v.getInt16(48, true)].join(','));
});
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    assert esito.stdout.strip() == "32767,-32767,0"

def test_i_campioni_del_microfono_arrivano_a_16_khz(client):
    """Il microfono non consegna sempre 16 kHz: l'audio breve ne accetta uno solo,
    quindi si riscrive. Sbagliare qui manda audio che il servizio non legge."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("const ASCOLTO_CAMPIONI"):js.index("\n}\n", js.index("function aSediciKhz")) + 3]
    prova = blocco + """
// 48 kHz -> 16 kHz: un campione ogni tre
const alti = new Float32Array(48000);
for (let i = 0; i < alti.length; i++) alti[i] = Math.sin(i / 100);
const fuori = aSediciKhz(alti, 48000);
// già a 16 kHz: non si tocca niente
const stessi = new Float32Array([0.1, 0.2, 0.3]);
console.log(JSON.stringify({
  lunghezza: fuori.length, attesa: 16000,
  intatti: aSediciKhz(stessi, 16000) === stessi,
}));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    d = json.loads(esito.stdout)
    assert d["lunghezza"] == d["attesa"]
    assert d["intatti"] is True

def test_il_browser_bloccato_ma_senza_chiave_suggerisce_la_chiave(client):
    """Il caso che l'utente ha davanti: Chrome risponde "network" e il server non
    ha la chiave Azure, quindi non puo' trascrivere al posto del browser.

    Il messaggio non puo' limitarsi a "scrivi qui sotto": la chiave Azure e' la
    soluzione vera al blocco, e va detta proprio allora. Si esegue la funzione
    con node, cosi' il test verifica **quale** messaggio esce, non che una frase
    sia scritta nel file.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function messaggioMicrofono"):
                 js.index("\n}\n", js.index("function messaggioMicrofono")) + 3]
    prova = blocco + """
console.log(JSON.stringify({
  senzaChiave: messaggioMicrofono('network', false),
  conChiave: messaggioMicrofono('network', true),
  negato: messaggioMicrofono('not-allowed', false),
}));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    d = json.loads(esito.stdout)
    # senza chiave: si dice che la chiave sposta la trascrizione sul server
    assert "chiave" in d["senzaChiave"].lower()
    assert "server" in d["senzaChiave"].lower()
    # con la chiave gia' attiva quel consiglio non ha senso: non va ripetuto
    assert "chiave" not in d["conChiave"].lower()
    # gli altri errori non si toccano
    assert "autorizzato" in d["negato"].lower()
    # e la funzione dev'essere quella che l'errore del microfono usa davvero:
    # verificata da sola non servirebbe a niente se restasse scollegata
    assert "voceStato(messaggioMicrofono(e.error, voceCloud.ascolto), 'err');" in js

def test_dopo_dimmi_il_comando_si_dice_senza_ripetere_la_sveglia(client):
    """Il dialogo naturale, ed era rotto: si chiama "maggiordomo", lui risponde
    "Dimmi.", e la frase successiva è il comando — senza ripetere la sveglia.

    Prima il ciclo pretendeva di nuovo la sveglia anche lì: il comando veniva
    ignorato **in silenzio**, che è il peggior modo di fallire. Qui si verifica
    che dentro la finestra il comando parta.
    """
    d = _decisione_js(client, """{
      // la sveglia da sola apre la finestra, non esegue
      soloSveglia: decisioneContinuo('Maggiordomo.', true, '', false),
      // il comando detto subito dopo, senza sveglia: deve partire
      dopoDimmi: decisioneContinuo('metti il latte nella spesa', false, '', true),
      // e deve partire anche una domanda, che è un comando come gli altri
      domanda: decisioneContinuo("che cosa c'è in dispensa", false, '', true),
    }""")
    assert d["soloSveglia"]["azione"] == "chiedi"
    assert d["dopoDimmi"] == {"azione": "esegui", "comando": "metti il latte nella spesa"}
    assert d["domanda"]["azione"] == "esegui"

def test_fuori_dalla_finestra_la_sveglia_serve_di_nuovo(client):
    """La finestra è a tempo, non per sempre.

    Senza questo limite, una volta chiamato l'assistente ogni frase di casa
    diventerebbe un ordine: "il maggiordomo prepara la cena", detto a tavola,
    scriverebbe in dispensa.
    """
    d = _decisione_js(client, """{
      fuoriFinestra: decisioneContinuo('metti il latte nella spesa', false, '', false),
      chiacchiera: decisioneContinuo('il maggiordomo prepara la cena', false, '', true),
      nonComando: decisioneContinuo('oggi c\\u00e8 il sole', false, '', true),
    }""")
    assert d["fuoriFinestra"]["azione"] == "ignora"
    # anche dentro la finestra, una frase che non è un ordine resta fuori
    assert d["chiacchiera"]["azione"] == "ignora"
    assert d["nonComando"]["azione"] == "ignora"

def test_un_comando_senza_sveglia_lo_dice_invece_di_tacere(client):
    """Il caso del telefono: la frase viene trascritta, l'utente la legge, e poi
    non succede **nulla**. Succede quando il comando non contiene la sveglia e la
    finestra non e' aperta: la decisione e' `ignora`, e l'app taceva del tutto.

    Tacere nel suono va bene (l'ascolto continuo non risponde al discorso di
    casa), ma tacere anche sullo **schermo** lascia chi ha parlato senza sapere
    se e' stato sentito. Un ordine senza la sveglia deve dire che manca la
    sveglia; una chiacchiera di casa resta muta come prima."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "Non ho eseguito" in js and "Hey GG" in js
    # la frase sentita si mostra comunque: dice cosa ha capito
    assert "$('#voice-heard').textContent = frase || '…';" in js
    # e l'avviso si da' solo a una frase che sembra un comando
    blocco = js[js.index("const frase = (testo || '').trim();"):]
    blocco = blocco[:blocco.index("riparti();") + len("riparti();")]
    assert "sembraComando(frase)" in blocco

def test_una_chiacchiera_dopo_dimmi_non_diventa_un_ordine(client):
    """Il rischio della finestra: una volta chiamato l'assistente, il discorso di
    casa che segue non deve trasformarsi in un ordine.

    "il maggiordomo prepara la cena", detto a tavola dopo un "Dimmi.", scriverebbe
    in dispensa. Il criterio è lo stesso della sveglia: la parola che apre la
    frase decide."""
    d = _decisione_js(client, """{
      chiacchiera: decisioneContinuo('il maggiordomo prepara la cena', false, '', true),
      discorso: decisioneContinuo('oggi viene mia madre a pranzo', false, '', true),
      // invece una frase che apre con un numero è una dose, e vale
      dose: decisioneContinuo('due chili di farina', false, '', true),
    }""")
    assert d["chiacchiera"]["azione"] == "ignora"
    assert d["discorso"]["azione"] == "ignora"
    assert d["dose"]["azione"] == "esegui"

def test_la_sveglia_con_il_comando_esegue_senza_finestra(client):
    """Il caso più comune: "maggiordomo, metti il latte". Non serve nessuna
    finestra, il comando è nella frase stessa."""
    d = _decisione_js(client, """{
      insieme: decisioneContinuo('Maggiordomo, metti il latte nella spesa', true,
                                 'metti il latte nella spesa', false),
    }""")
    assert d["insieme"] == {"azione": "esegui", "comando": "metti il latte nella spesa"}

def test_la_domanda_sulla_quantita_vale_senza_sveglia(client):
    """Il difetto riferito: dopo aver chiamato l'assistente, comandi come
    "quante ricette ho" venivano **ignorati in silenzio**, e sembrava che
    servisse dire "Hey GG" ogni volta.

    La causa: il criterio che apre la frase (`sembraComando`) accettava "quanto"
    ma non "quante"/"quanti"/"quanta", che sono la forma piu' naturale ("quante
    uova ho?", "quanti grammi sono rimasti"). Il parser del server li capisce
    (intento `domanda`), quindi era solo il cancello a sbarrarli."""
    d = _decisione_js(client, """{
      quanteRicette: decisioneContinuo('quante ricette ho', false, '', true),
      quantiGrammi: decisioneContinuo('quanti grammi sono rimasti', false, '', true),
      quantaFarina: decisioneContinuo('quanta farina ho', false, '', true),
      quantoSale: decisioneContinuo('quanto sale ho', false, '', true),
    }""")
    for caso in ("quanteRicette", "quantiGrammi", "quantaFarina", "quantoSale"):
        assert d[caso]["azione"] == "esegui", (caso, d[caso])
    # e la forma resta fuori **fuori** dalla finestra, come ogni comando
    d2 = _decisione_js(client, """{
      fuori: decisioneContinuo('quante ricette ho', false, '', false),
    }""")
    assert d2["fuori"]["azione"] == "ignora"

def test_la_finestra_dopo_si_si_riarma_dopo_un_comando(client):
    """Il secondo pezzo del difetto: la finestra si chiudeva col **primo**
    comando, quindi "Hey GG", "metti il latte", "e aggiungi il pane" richiedeva
    la sveglia a ogni frase. Ora dopo un comando si rinnova, cosi' piu' ordini
    di fila si dicono dopo una sola attivazione.

    Il tetto resta: la finestra non e' eterna, altrimenti il discorso di casa
    diventerebbe un ordine."""
    d = _finestra_js(client, """
attendeComando();                       // t=0: si apre
const subito = inAttesaComando();       // true
avanza(9000);
riarmaFinestra();                       // t=9000: un comando la rinnova
avanza(6000);                           // t=15000
const dopoComando = inAttesaComando();  // true: 15s - 9s < 10s
avanza(5000);                           // t=20000: 20s - 9s = 11s > 10s
const scaduta = inAttesaComando();      // false
console.log(JSON.stringify({ subito, dopoComando, scaduta }));
""")
    assert d == {"subito": True, "dopoComando": True, "scaduta": False}, d

def test_la_finestra_ha_un_tetto_e_non_si_apre_da_sola(client):
    """Due guardie opposte, entrambe necessarie:

    - `riarmaFinestra` **non** apre una finestra chiusa: altrimenti bastava un
      comando qualunque per far entrare il discorso di casa;
    - una raffica di comandi non tiene la finestra aperta per sempre: il tetto
      si misura dall'apertura, non dall'ultimo comando."""
    d = _finestra_js(client, """
// chiusa: riarmare non apre
riarmaFinestra();
const chiusaRestaChiusa = inAttesaComando();
// aperta, con comandi a raffica ogni 9 s
attendeComando();
for (let i = 0; i < 5; i++) { avanza(9000); riarmaFinestra(); }
avanza(1000);                            // t = 46 s dall'apertura
const oltreIlTetto = inAttesaComando();  // il tetto e' 30 s
console.log(JSON.stringify({ chiusaRestaChiusa, oltreIlTetto }));
""")
    assert d == {"chiusaRestaChiusa": False, "oltreIlTetto": False}, d

def test_dopo_un_comando_la_finestra_non_si_azzera(client):
    """Il legame che rende utile il riarmo: nel ramo `esegui` si chiama
    `riarmaFinestra()`. Con il vecchio `inAttesa = 0` il secondo ordine di fila
    veniva ignorato in silenzio — il difetto riferito."""
    js = client.get("/static/app.js").get_data(as_text=True)
    ramo = js[js.index("if (d.azione === 'esegui')"):]
    ramo = ramo[:ramo.index("eseguiComandoContinuo(")]
    assert "riarmaFinestra()" in ramo
    assert "inAttesa = 0" not in ramo

def test_il_microfono_prova_prima_il_server(client):
    """La strada giusta è il server: è quello che esce dalla rete. Il browser
    resta il ripiego, per quando la chiave non c'è."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "/api/voce/ascolta" in js
    assert "ascoltaSulServer" in js and "ascoltaDalBrowser" in js
    # il dispatcher sceglie il server quando è disponibile
    assert "if (voceCloud.ascolto && ascoltaSulServer(esitoAscolto, { tenuto })) return;" in js
    # e il 503 non è un errore da mostrare: si ripiega sul browser
    assert "if (d && d.ripiega) { ascoltaDalBrowser(); return; }" in js

def test_la_registrazione_si_ferma_da_sola_fine_frase(client):
    """Senza la fine automatica il microfono resterebbe aperto finché non lo si
    chiude a mano, e nessuno lo chiude: la frase non partirebbe mai."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "fineRegistrazione" in js
    assert "ASCOLTO_MAX_MS" in js
    d = _fine_registrazione_js(client, """{
      // si sta parlando, l'ultimo suono e' recente: non chiudere
      parlando: fineRegistrazione({inizio: 0, ultimoSuono: 1000, parlatoDa: true, adesso: 1200}),
      // si e' smesso di parlare da un pezzo: chiudere
      finePausa: fineRegistrazione({inizio: 0, ultimoSuono: 1000, parlatoDa: true, adesso: 3000}),
      // nessuno parla ancora: chiudere dopo l'attesa
      silenzioLungo: fineRegistrazione({inizio: 0, ultimoSuono: 0, parlatoDa: false, adesso: 7000}),
      // e non chiudere troppo presto
      silenzioBreve: fineRegistrazione({inizio: 0, ultimoSuono: 0, parlatoDa: false, adesso: 3000}),
      // il tetto chiude qualunque cosa succeda
      tetto: fineRegistrazione({inizio: 0, ultimoSuono: 999999, parlatoDa: true, adesso: 16000}),
    }""")
    assert d["parlando"] is False
    assert d["finePausa"] is True
    assert d["silenzioLungo"] is True
    assert d["silenzioBreve"] is False
    assert d["tetto"] is True

def test_la_registrazione_non_resta_appesa_senza_campioni(client):
    """Il guasto del telefono, riprodotto: la spia dice "in ascolto" ma non passa
    mai a "Trascrivo…". La causa era che su iPhone `onaudioprocess` non scatta, e
    la chiusura della frase dipendeva **solo** da li': la registrazione restava
    appesa per sempre. Qui si esegue `ascoltaSulServer` **vera** con un
    `AudioContext` finto il cui callback dei campioni non viene mai chiamato, e
    si verifica che l'esito arrivi comunque, dal timer di sicurezza."""
    esito = _ascolta_senza_campioni_js(client)
    assert esito["gestoreAssegnato"] is True, "il registratore deve essersi avviato"
    assert esito["campioniChiamati"] is False, "il caso da riprodurre: nessun campione"
    assert esito["esitoRicevuto"] is True, (
        "senza campioni la registrazione deve chiudersi lo stesso")
    assert esito["ms"] < 2000, f"ci ha messo troppo: {esito['ms']} ms"
    # e l'esito lo dice: tacere sembrerebbe che l'app sia sorda
    assert esito["muto"] is True, "l'app deve accorgersi del microfono muto"

def test_il_microfono_muto_non_tace_per_sempre(client):
    """Se il microfono non manda **nessun** campione, l'app deve dirlo: tacere
    con la spia "in ascolto" e' il modo peggiore di fallire, perche' sembra che
    l'app sia sorda. Si riproduce il caso con `ascoltaSulServer` vera e un
    microfono finto muto."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "muto" in js
    assert "Il microfono non manda audio" in js

def test_il_ciclo_ha_un_battito_e_un_sorvegliante(client):
    """Un giro perso (microfono che non consegna l'audio) lasciava l'ascolto
    acceso ma sordo, senza nessun errore. Il battito dice che il ciclo e' vivo,
    e il sorvegliante lo fa ripartire quando non batte piu'."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "battito" in js
    assert "function sorvegliaIlCiclo(" in js
    assert "BATTITO_MASSIMO_MS" in js
    d = _sorvegliante_js(client, """{
      // appena acceso: il ciclo ha battuto, non intervenire
      fresco: cicloDaRiavviare(1000, 5000),
      // fermo da troppo, e non sta parlando: riavviare
      fermo: cicloDaRiavviare(1, 40000),
      // sta parlando (sospeso): attesa voluta, non e' un guasto
      sospeso: cicloDaRiavviare(1, 40000, true),
      // aspetta un tocco del browser: c'e' gia' il suo avviso
      gesto: cicloDaRiavviare(1, 40000, false, true),
    }""")
    assert d["fresco"] is False
    assert d["fermo"] is True, "un ciclo morto va fatto ripartire"
    assert d["sospeso"] is False
    assert d["gesto"] is False

def test_lo_stato_dell_ascolto_dice_chi_ascolta(client):
    """Il guasto che risolve: senza chiave l'ascolto ripiega in silenzio sul
    browser, e l'utente crede che l'app sia rotta. La riga dice **chi** ascolta e
    **cosa manca**, cosi' la stessa situazione e' una cosa da accendere."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "statoAscoltoTesto" in js
    assert "voice-stato-ascolto" in js
    d = _stato_ascolto_js(client, """{
      server: statoAscoltoTesto({ ascoltoServer: true, contesto: true }),
      browser: statoAscoltoTesto({ ascoltoServer: false, contesto: true }),
      insicuro: statoAscoltoTesto({ ascoltoServer: true, contesto: false }),
    }""")
    assert "server" in d["server"].lower() and "azure" in d["server"].lower()
    assert "browser" in d["browser"].lower()
    assert "chiave" in d["browser"].lower(), "senza server deve dire cosa manca"
    # il contesto non sicuro vince su tutto: e' quello che impedisce il microfono.
    # Il rimedio (HTTPS/localhost) sta nell'avviso dedicato, non qui: la riga dice
    # solo che l'ascolto non e' disponibile, senza promettere Azure.
    assert "non disponibile" in d["insicuro"].lower()
    assert "azure" not in d["insicuro"].lower()

def test_il_verdetto_del_microfono_dice_quale_controllo_ha_fermato(client):
    """La prova del microfono deve dire **quale** controllo ha fermato cosa,
    invece di lasciare il pulsante muto."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "verdettoMicrofono" in js
    d = _verdetto_microfono_js(client, """{
      ok: verdettoMicrofono({ contesto: true, haApi: true, permesso: 'granted', bloccato: false }),
      insicuro: verdettoMicrofono({ contesto: false, haApi: true, permesso: '', bloccato: false }),
      senzaApi: verdettoMicrofono({ contesto: true, haApi: false, permesso: '', bloccato: false }),
      negato: verdettoMicrofono({ contesto: true, haApi: true, permesso: 'denied', bloccato: false }),
      bloccato: verdettoMicrofono({ contesto: true, haApi: true, permesso: 'granted', bloccato: true }),
    }""")
    assert d["ok"]["esito"] == "ok"
    assert d["insicuro"]["esito"] == "no"
    assert d["senzaApi"]["esito"] == "no"
    assert d["negato"]["esito"] == "no"
    assert d["bloccato"]["esito"] == "bloccato", "il blocco audio non e' 'no': si sblocca con un tocco"
    assert "https" in d["insicuro"]["testo"].lower() or "localhost" in d["insicuro"]["testo"].lower()
    assert "autorizzato" in d["negato"]["testo"].lower()
    assert "tocca" in d["bloccato"]["testo"].lower()

def test_il_push_to_talk_si_adatta_al_dispositivo(client):
    """Sul telefono il tocco e' un inizio e una fine insieme: il toggle a due
    tocchi si sbaglia. Col dito si tiene premuto, col mouse e' un interruttore."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "modoParla" in js and "voice-parla" in js
    d = _modo_parla_js(client, """{
      dito: modoParla(true),
      mouse: modoParla(false),
      // il dito che scorre fuori dal pulsante non deve perdere la frase
      rilascio: guardaSeRilascia({ pushAttivo: true, dentro: true, tipo: 'leave' }),
      uscito: guardaSeRilascia({ pushAttivo: true, dentro: false, tipo: 'leave' }),
      su: guardaSeRilascia({ pushAttivo: true, dentro: true, tipo: 'up' }),
      spento: guardaSeRilascia({ pushAttivo: false, dentro: false, tipo: 'up' }),
    }""")
    assert d["dito"] == "push"
    assert d["mouse"] == "toggle"
    assert d["rilascio"] is False, "un dito ancora dentro non chiude la frase"
    assert d["uscito"] is True
    assert d["su"] is True
    assert d["spento"] is False, "senza push attivo non c'e' niente da chiudere"

def test_la_prova_del_microfono_esiste_e_non_esegue_il_comando(client):
    """La prova dice cosa non va, ma non deve scrivere in dispensa: chi prova
    vuole sapere se il microfono funziona, non modificare i dati."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "provaMicrofono" in js
    assert "voice-prova" in js
    assert "voice-prova-esito" in js
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="voice-prova"' in html
    assert 'id="voice-prova-esito"' in html
    # il ramo della prova deve essere prima dell'esecuzione del comando
    i_prova = js.index("if (voce.provaMicrofono) {", js.index("function esitoAscolto"))
    i_esegui = js.index("eseguiComando(testo);", js.index("function esitoAscolto"))
    assert i_prova < i_esegui, "la prova deve intercettare l'esito prima di eseguire"
    assert "fineProvaMicrofono" in js

def test_l_ascolto_non_tenta_a_vuoto_da_un_indirizzo_non_sicuro(client):
    """Da http://IP il browser non da' il microfono: l'app deve dirlo e portare al
    campo di testo, invece di aprire un microfono che non sentira' mai."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "senzaMicrofono" in js
    assert "isSecureContext" in js
    assert "mostraSenzaMicrofono" in js
    # il pulsante del microfono flottante resta raggiungibile: apriVoce() non
    # tenta la registrazione quando il contesto non e' sicuro
    assert "if (voce.senzaMicrofono) {" in js

def test_la_pagina_spiega_perche_la_voce_e_robotica(client):
    """Senza chiave la voce e' quella del sistema: il pannello del microfono, dove
    la voce si sente, deve dirlo e indicare come avere quella naturale. (La scheda
    "Voce" delle FAQ, che lo ripeteva, e' stata rimossa su richiesta.)"""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "mostraAvvisoRobotica" in js
    assert "voice-chiave-manca" in js
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="voice-chiave-manca"' in html
    assert "voce naturale" in html

def test_la_pagina_avvisa_se_il_microfono_non_puo_funzionare(client):
    """Da http:// su rete locale il riconoscimento vocale e' negato dal browser."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "isSecureContext" in js and "mostraAvvisoSicurezza" in js

def test_la_pagina_non_gestisce_la_chiave(client):
    """La chiave si configura **prima** di avviare l'app, non dall'utente in FAQ.

    Un campo chiave nella pagina significherebbe che l'app puo' scrivere il
    segreto: chi apre la pagina potrebbe cambiarlo, e la chiave finirebbe in una
    richiesta HTTP. Il posto giusto e' accanto al programma, fuori da git.
    """
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="voice-chiave"' not in html
    assert 'id="voice-chiave-salva"' not in html
    assert 'id="voice-chiave-dettagli"' not in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "salvaChiaveVoce" not in js
    assert "/api/voce/configura" not in js

def test_l_endpoint_che_salvava_la_chiave_non_esiste_piu(client):
    """Senza la rotta non c'e' modo di scrivere il segreto via HTTP: la chiave
    entra solo dal file o dall'ambiente, prima dell'avvio."""
    r = client.post("/api/voce/configura", json={"chiave": "x", "regione": "italynorth"})
    assert r.status_code in (404, 405), r.status_code

def test_il_pannello_del_microfono_dice_di_configurare_prima(client):
    """Senza la chiave la voce e' meccanica, e il pannello del microfono e' dove
    l'utente la sente: deve dire **dove** si mette, e non mandarlo in una pagina
    che non la chiede piu'."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="voice-chiave-manca"' in html
    inizio = html.index('id="voice-chiave-manca"')
    avviso = html[inizio:inizio + 400]
    assert "prima di avviare" in avviso
    assert "FAQ" not in avviso
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "voice-chiave-manca" in js

def test_gli_spazi_ai_bordi_della_password_non_contano(casa_test):
    """Uno spazio incollato per sbaglio non si vede, e l'errore non lo dice."""
    for scritta in [PASSWORD_TEST, PASSWORD_TEST + " ", " " + PASSWORD_TEST, "  " + PASSWORD_TEST + "  "]:
        assert houses.autentica(CASA_TEST, scritta), f"rifiutata: {scritta!r}"

def test_una_password_sbagliata_resta_sbagliata(casa_test):
    """Tollerare gli spazi non deve far entrare chi non sa la password."""
    for scritta in ["sbagliata", PASSWORD_TEST[:-1], PASSWORD_TEST + "x", ""]:
        assert not houses.autentica(CASA_TEST, scritta), f"entrata con: {scritta!r}"

def test_la_password_salvata_non_tiene_gli_spazi(tmp_path):
    """Salvata con uno spazio ai bordi, si salva la parte che conta."""
    registro = str(tmp_path / "houses.db")
    slug = houses.crea("Casa Spazi", "  PasswordConSpazi  ", percorso=registro)
    assert houses.autentica(slug, "PasswordConSpazi", percorso=registro)
    assert houses.autentica(slug, "PasswordConSpazi ", percorso=registro)

def test_l_accesso_accetta_la_password_con_spazio_finale(client):
    """Il giro completo: dalla pagina, con lo spazio che il copia-incolla aggiunge."""
    r = client.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST + " "})
    assert r.status_code == 200

def test_la_pagina_fa_vedere_la_password(client):
    """Il campo e' nascosto: senza vederla, uno spazio non si nota."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="acc-mostra"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "acc-mostra" in js and "acc-password" in js

def test_la_pagina_non_resta_in_memoria_nel_browser(anon):
    """Senza questo, una pagina vecchia resta nel browser e l'app sembra
    non aggiornata: e' successo davvero, e per giorni."""
    r = anon.get("/")
    assert r.status_code == 200
    # 'no-cache' basta: dice al browser di richiedere la pagina prima di usarla
    assert "no-cache" in r.headers.get("Cache-Control", "")
    js = anon.get("/static/app.js")
    assert "no-cache" in js.headers.get("Cache-Control", "")

def test_le_immagini_dei_dati_restano_in_memoria(client):
    """La' la memoria serve: una foto non cambia, e riscaricarla a ogni vista
    sarebbe uno spreco."""
    # i dati veri e propri passano dall'API e non si tengono; le foto, che non
    # cambiano, scelgono da sole la loro scadenza in una rotta apposita
    r = client.get("/api/recipes")
    assert "no-cache" in r.headers.get("Cache-Control", "")

def test_gli_asset_hanno_la_versione_nell_indirizzo(client):
    """`app.js` e `style.css` non hanno un indirizzo che cambia: senza un numero
    di versione il browser non sa che sono nuovi e continua a usarne una copia.
    La versione e' un'impronta del contenuto, quindi cambia solo quando il file
    cambia."""
    html = client.get("/").get_data(as_text=True)
    assert "/static/app.js?v=" in html
    assert "/static/style.css?v=" in html
    # la versione e' quella vera del file: la stessa cosa che darebbe l'impronta
    js = client.get("/static/app.js").get_data(as_text=True)
    import hashlib
    attesa = hashlib.sha256(js.encode("utf-8")).hexdigest()[:10]
    assert f"/static/app.js?v={attesa}" in html

def test_un_asset_versionato_resta_in_memoria_a_lungo(client):
    """Con la versione nell'indirizzo tenere la copia a lungo e' sicuro: se il
    file cambia cambia anche l'indirizzo, quindi non si vede mai una versione
    vecchia. E' quello che evita di riscaricare 200 KB a ogni apertura."""
    r = client.get("/static/app.js?v=qualsiasi")
    assert "max-age=31536000" in r.headers.get("Cache-Control", "")
    assert "immutable" in r.headers.get("Cache-Control", "")

def test_le_intestazioni_di_sicurezza_ci_sono_su_tutte_le_risposte(client, anon):
    """Le intestazioni di sicurezza non stanno nel ramo della cache, che per gli
    asset versionati esce presto: devono esserci **sempre**, anche su un 404 e su
    un asset. Senza, una pagina sola basterebbe per un clickjacking."""
    for r in (client.get("/"), client.get("/api/meta"),
              client.get("/static/app.js?v=1"), anon.get("/pagina-che-non-esiste")):
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "microphone=(self)" in r.headers.get("Permissions-Policy", "")
        assert "Content-Security-Policy" in r.headers

def test_la_csp_consente_solo_il_necessario(client):
    """La CSP deve permettere esattamente cio' che l'app usa e niente di piu':
    gli iframe dei video, le locandine di TMDB, l'audio blob della voce. E non
    deve contenere `'unsafe-inline'` per gli script, che vanificherebbe la
    difesa contro uno script iniettato."""
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "frame-src https://www.youtube-nocookie.com" in csp
    assert "img-src 'self' data: https://image.tmdb.org https://images.metmuseum.org" in csp
    assert "media-src 'self' blob: data:" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    # il punto che conta: `script-src` non ha `'unsafe-inline'`
    script_src = csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "'unsafe-inline'" not in script_src

def test_gli_script_inline_portano_il_nonce_e_gli_altri_no(client):
    """Gli unici script inline (tema e service worker) prendono un nonce per
    pagina, e il nonce e' quello annunciato nella CSP: senza, il browser non li
    esegue e il tema scuro non si applica prima del disegno."""
    r = client.get("/")
    html = r.get_data(as_text=True)
    csp = r.headers["Content-Security-Policy"]
    nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
    # ogni script inline ha il nonce, nessuno resta senza
    assert html.count(f'<script nonce="{nonce}">') == 2
    assert "<script>" not in html
    # gli script con `src` sono coperti da `'self'` e non portano il nonce
    assert f'<script src="/static/app.js' in html
    # il nonce cambia a ogni pagina: se fosse fisso, un iniettore lo leggerebbe
    altro = re.search(r"'nonce-([^']+)'", client.get("/").headers["Content-Security-Policy"]).group(1)
    assert altro != nonce

def test_il_service_worker_si_serve_dalla_radice_e_senza_accesso(anon):
    """Il service worker controlla solo il percorso da cui e' servito: da
    `/static/` non potrebbe mostrare la pagina `/` senza rete. E non chiede
    l'accesso, perche' deve poter partire prima del login."""
    r = anon.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.headers.get("Content-Type", "")
    assert "caches" in r.get_data(as_text=True)

def test_la_pagina_registra_il_service_worker(client):
    """La registrazione sta nella pagina, non in `app.js`: cosi' parte anche se
    il codice dell'app non e' stato ancora caricato."""
    html = client.get("/").get_data(as_text=True)
    assert "serviceWorker" in html and "register('/sw.js')" in html

def test_i_file_statici_si_chiedono_prima_alla_rete(client):
    """Il service worker serviva `app.js` **prima dalla copia**: `chiave()`
    ignora `?v=...`, quindi la copia salvata all'installazione (senza versione)
    rispondeva a qualunque richiesta, anche a una versione nuova. Risultato: la
    pagina (`index.html`, prima la rete) si aggiornava, `app.js` restava vecchio,
    e una funzione nuova — come il calendario in home — non veniva mai disegnata.
    Qui si esegue `serveStatico` vera: con la rete su deve vincere la rete,
    non la copia; con la rete giu' deve reggere la copia."""
    js = client.get("/static/sw.js").get_data(as_text=True)
    chiave = _estrai_funzione_js(js, "chiave")
    blocco = _estrai_funzione_js(js, "serveStatico")
    preludio = """
const CACHE = 'prova';
let reteOk = true;
const salvati = { 'http://a/static/app.js': { corpo: 'VECCHIO' } };
globalThis.caches = {
  open: async () => ({
    put: async (k, v) => { salvati[k] = v; },
    match: async (k) => salvati[k],
  }),
  match: async (k) => salvati[k],
};
globalThis.fetch = async () => {
  if (!reteOk) throw new Error('offline');
  return { ok: true, corpo: 'NUOVO', clone() { return this; } };
};
"""
    coda = """
(async () => {
  const online = await serveStatico({ url: 'http://a/static/app.js?v=123' });
  reteOk = false;
  const offline = await serveStatico({ url: 'http://a/static/app.js?v=999' });
  console.log(JSON.stringify({ online: online.corpo, offline: offline.corpo,
    salvato: salvati['http://a/static/app.js'].corpo }));
})();
"""
    d = _esegui_node(preludio + chiave + blocco + coda)
    assert d["online"] == "NUOVO", "con la rete su deve arrivare la versione nuova, non la copia"
    assert d["salvato"] == "NUOVO", "la copia va aggiornata con la versione nuova"
    assert d["offline"] == "NUOVO", "senza rete deve reggere l'ultima copia buona"

def test_una_domanda_non_diventa_un_ordine(client):
    """La frase che assomiglia di piu' a un comando e' una domanda: contiene un
    luogo ("dispensa") e un verbo ("c'e'"). Eseguita, scriveva in dispensa una
    voce chiamata "che cosa c'e in dispensa", e la voce sbagliata resta li'."""
    prima = len(client.get("/api/pantry").get_json())
    r = client.post("/api/voice", json={"text": "che cosa c'è in dispensa"})
    assert r.status_code == 200
    assert r.get_json()["intent"] == "domanda"
    assert len(client.get("/api/pantry").get_json()) == prima

def test_una_domanda_su_un_alimento_ne_dice_la_quantita(client):
    """ "quanto sale serve" e' la domanda piu' naturale che ci sia: deve
    rispondere, non finire in lista della spesa."""
    client.post("/api/pantry", json={"name": "Sale", "quantity": 1, "unit": "cucchiaino"})
    r = client.post("/api/voice", json={"text": "quanto sale serve"})
    assert r.status_code == 200
    assert "Sale" in r.get_json()["message"]
    lista = client.get("/api/shopping").get_json()
    assert not any("sale" in i["name"].lower() and "serve" in i["name"].lower() for i in lista)

def test_una_domanda_senza_risposta_non_inventa_niente(client):
    r = client.post("/api/voice", json={"text": "che cosa c'è in dispensa"})
    assert r.status_code == 200
    assert "vuot" in r.get_json()["message"].lower()

def test_un_ordine_resta_un_ordine(client):
    """Le domande non devono rubare il posto ai comandi veri."""
    r = client.post("/api/voice", json={"text": "aggiungi due chili di farina in dispensa"})
    assert r.get_json()["intent"] == "pantry_add"
    r = client.post("/api/voice", json={"text": "segna il pane da comprare"})
    assert r.get_json()["intent"] == "shopping_add"

def test_le_domande_su_ricette_e_pulizie_rispondono(client):
    r = client.post("/api/voice", json={"text": "quante ricette ho"})
    assert r.status_code == 200 and r.get_json()["intent"] == "domanda"
    assert "ricett" in r.get_json()["message"].lower()
    r = client.post("/api/voice", json={"text": "quali pulizie devo fare"})
    assert r.status_code == 200 and r.get_json()["intent"] == "domanda"

def test_il_microfono_non_si_rompe_al_primo_clic(client):
    """Il primo clic apre il pannello e arriva ad `ascolta()` senza nessun
    riconoscimento avviato. Chiamare `stop()` su niente sollevava un errore
    invisibile e il microfono restava muto: era il guasto da PC."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "voce.attivo && voce.rec" in js
    assert "if (voce.attivo) { voce.rec.stop(); return; }" not in js

def test_la_dispensa_mostra_un_icona_per_alimento(client):
    """Un'icona dice a colpo d'occhio di cosa si tratta, prima di leggerlo."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "iconaAlimento" in js and "icona-alimento" in js
    html = client.get("/static/index.html").get_data(as_text=True)
    assert "pantry-table" in html

def test_le_icone_degli_alimenti_sono_scelte_bene(client):
    """Le parole corte non devono entrare dentro le altre: "te" sta in
    "detersivo", e il detersivo non e' una bevanda."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("const ICONE_CATEGORIA"):js.index("\n}\n", js.index("function iconaAlimento")) + 3]
    prova = blocco + """
const casi = [
  ['Farina 00', 'Pane e Cereali', '🌾'],
  ['Passata di pomodoro', 'Dispensa', '🍅'],
  ['Aglio', 'Frutta e Verdura', '🧄'],
  ['Parmigiano', 'Latticini', '🧀'],
  ['Guanciale', 'Carne e Pesce', '🥓'],
  ['Tonno', 'Carne e Pesce', '🐟'],
  ['Detersivo piatti', 'Altro', '🧴'],
  ['Detergente', 'Altro', '🧴'],
  ['Te nero', 'Bevande', '🍵'],
  ['Pile stilo', 'Altro', '🔋'],
  ['Cosa mai vista', 'Altro', '📦'],
];
let esiti = [];
for (const [n, c, atteso] of casi) {
  const avuto = iconaAlimento(n, c);
  esiti.push(`${avuto === atteso ? 'ok' : 'NO'} ${n} -> ${avuto} (atteso ${atteso})`);
}
console.log(esiti.join('\\n'));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    assert "NO " not in esito.stdout, esito.stdout

def test_la_voce_porta_gli_ingredienti_nel_modulo(client):
    """Gli ingredienti dettati arrivano davvero nel modulo, non solo nella risposta.

    Si esegue la funzione vera con node: un test sulle stringhe non accorgerebbe
    di un `nuovaRicetta(res.name)` che si dimentica il secondo argomento, e il
    modulo si aprirebbe vuoto mentre i test del server restano verdi.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function nuovaRicetta")
    blocco = js[inizio:js.index("\n}\n", inizio) + 3]
    prova = """
const finte = [];
let chiamataRecipeForm = null;
global.showModal = (titolo, corpo) => { global._corpo = corpo; };
global.$ = (sel) => ({ addEventListener: (ev, fn) => finte.push([sel, fn]) });
global.esc = (s) => String(s ?? '');
global.recipeForm = (...args) => { chiamataRecipeForm = args; };
global.cercaRicettaOnline = () => {};
""" + blocco + """
const ingredienti = [{ name: 'pasta', quantity: 500, unit: 'g' }];
nuovaRicetta('pasta al forno', ingredienti);
const esiti = [];
esiti.push((global._corpo.includes('pasta') ? 'ok' : 'NO') + ' ingredienti annunciati');
finte.find(([sel]) => sel === '#ric-scrivi')[1]();
esiti.push((chiamataRecipeForm && chiamataRecipeForm[0] === null
  && chiamataRecipeForm[1] === 'pasta al forno'
  && chiamataRecipeForm[2] === ingredienti ? 'ok' : 'NO') + ' ingredienti passati al modulo');
console.log(esiti.join('\\n'));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    assert "NO " not in esito.stdout, esito.stdout

def test_le_righe_degli_ingredienti_dettati_si_precompilano(client):
    """Le dosi dette finiscono nei campi giusti, e chi non ha unità non scrive
    "null".

    Si esegue `addRow` vero con node su un documento finto: un test sulle
    stringhe non vedrebbe un `value="null"` nel campo dell'unità, che l'utente
    leggerebbe come un dato inventato dall'app."""
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("const rowsBox = $('#ing-rows');")
    blocco = js[inizio:js.index("\n  (r.items.length", inizio)]
    prova = """
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const righe = [];
global.document = { createElement: () => ({ set innerHTML(v) { this._html = v; }, appendChild: () => {} }) };
global.$ = () => ({ appendChild: (div) => righe.push(div._html) });
""" + blocco + """
addRow({ name: 'pasta', quantity: 500, unit: 'g' });
addRow({ name: 'uova', quantity: 4, unit: null });
const esiti = [];
esiti.push((righe[0].includes('value="pasta"') && righe[0].includes('value="500"')
  && righe[0].includes('value="g"') ? 'ok' : 'NO') + ' dose completa');
esiti.push((righe[1].includes('value="uova"') && righe[1].includes('value="4"')
  && !righe[1].includes('null') ? 'ok' : 'NO') + ' unita assente senza null');
esiti.push((righe[1].includes('value="pz"') ? 'ok' : 'NO') + ' unita predefinita');
console.log(esiti.join('\\n'));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    assert "NO " not in esito.stdout, esito.stdout

def test_ogni_scheda_ricetta_ha_il_pulsante_piano(client):
    """Dal ricettario si aggiunge al piano con un pulsante, senza tornare nella
    scheda Piano: la ricetta si sceglie per quello che si vede (foto compresa).
    Il pulsante sta sulla scheda e apre `openPlanPicker`, non il selettore dei
    pasti vuoti (`openMealPicker`), che e' il verso opposto."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert 'data-plan="${r.id}"' in js
    # il click sul pulsante porta al selettore con la ricetta gia' scelta
    assert 'openPlanPicker(Number(planId))' in js
    # e il dettaglio della ricetta offre lo stesso, quando non e' gia' nel piano
    assert 'id="rd-plan"' in js
    assert "openPlanPicker(r, { conflicts: contesto.conflicts })" in js

def test_il_pulsante_piano_precompila_giorno_pasto_e_porzioni(client):
    """`openPlanPicker` costruisce il modulo con la ricetta gia' scelta: giorno
    (oggi preselezionato), pasto e porzioni della ricetta. Si esegue la funzione
    vera con node: un test sulle stringhe non vedrebbe un selettore vuoto."""
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function pastiDelGiorno")
    blocco = js[inizio:js.index("$('#week-prev')", inizio)]
    prova = """
const finte = [];
const valori = { '#pp-day': '2026-10-05', '#pp-meal': 'Cena', '#pp-serv': '4' };
global.showModal = (t, c) => { global._titolo = t; global._corpo = c; };
global.hideModal = () => { global._chiuso = true; };
global.$ = (sel) => ({ value: valori[sel] || '',
  addEventListener: (ev, fn) => finte.push([sel, fn]),
  classList: { contains: () => false } });
global.esc = (s) => String(s ?? '');
global.toast = () => {};
global.addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
global.iso = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
global.fmtDay = (d) => `giorno${d.getDate()}`;
global.weekStart = new Date(2026, 9, 5);
global.MEALS = ['Colazione', 'Pranzo', 'Cena'];
global.recipesCache = [{ id: 7, name: 'Carbonara', servings: 4, conflicts: [] }];
global.api = async (url, opts) => { global._chiamata = [url, opts]; return {}; };
""" + blocco + """
(async () => {
  await openPlanPicker(7);
  const esiti = [];
  esiti.push((global._titolo.includes('Carbonara') ? 'ok' : 'NO') + ' titolo con la ricetta');
  esiti.push((global._corpo.includes('id="pp-day"') && global._corpo.includes('Oggi')
    ? 'ok' : 'NO') + ' giorno con oggi preselezionato');
  esiti.push((global._corpo.includes('id="pp-meal"') && global._corpo.includes('>Cena<')
    ? 'ok' : 'NO') + ' pasti nel selettore');
  esiti.push((global._corpo.includes('id="pp-serv"') && global._corpo.includes('value="4"')
    ? 'ok' : 'NO') + ' porzioni della ricetta');
  finte.find(([sel]) => sel === '#pp-ok')[1]();
  await new Promise((r) => setTimeout(r, 0));
  const [, opts] = global._chiamata;
  esiti.push((opts.body.recipe_id === 7 && opts.body.meal === 'Cena'
    && opts.body.servings === 4 && opts.body.date === '2026-10-05'
    ? 'ok' : 'NO') + ' invio al piano con ricetta, pasto e porzioni');
  console.log(esiti.join('\\n'));
})();
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    assert "NO " not in esito.stdout, esito.stdout

def test_una_sessione_di_una_casa_eliminata_non_da_errore(anon):
    anon.post("/api/houses", json={"nome": "Casa A", "password": "aaaa"})
    houses.elimina("casa-a")
    info = anon.get("/api/session").get_json()
    assert info["authenticated"] is False

def test_ssml_ha_voce_lingua_e_prosodia():
    ssml = voce_cloud.costruisci_ssml("Ciao", "it-IT-IsabellaNeural", rate=1.2, pitch=-10)
    assert 'name="it-IT-IsabellaNeural"' in ssml
    assert 'xml:lang="it-IT"' in ssml
    assert 'rate="20%"' in ssml
    assert 'pitch="-10%"' in ssml
    assert ">Ciao<" in ssml

def test_ssml_senza_prosodia_non_aggiunge_tag():
    # a valori normali non deve comparire <prosody>: un tag inutile cambia la
    # lettura di alcune voci, e non c'e' ragione di generarlo
    ssml = voce_cloud.costruisci_ssml("Ciao", "it-IT-ElsaNeural")
    assert "<prosody" not in ssml
    assert ">Ciao<" in ssml

def test_ssml_mette_al_riparo_il_testo():
    # il testo arriva dall'utente e finisce dentro un XML: senza escape un "&"
    # farebbe fallire la sintesi, e un "<" potrebbe iniettare markup
    ssml = voce_cloud.costruisci_ssml("Sale & pepe <script>", "it-IT-ElsaNeural")
    assert "&amp;" in ssml
    assert "&lt;script&gt;" in ssml
    assert "<script>" not in ssml

def test_ssml_limita_i_valori_fuori_scala():
    # un rate assurdamente alto non deve passare ad Azure: si limita qui, dove il
    # comportamento e' prevedibile
    ssml = voce_cloud.costruisci_ssml("Ciao", "it-IT-ElsaNeural", rate=99, pitch=999)
    assert 'rate="100%"' in ssml      # 2.0 - 1
    assert 'pitch="50%"' in ssml      # tetto

def test_voci_italiane_ufficiali():
    nomi = {v["nome"] for v in voce_cloud.elenco_voci()}
    # nomi presi dall'elenco ufficiale Azure: inventarne uno lo farebbe rifiutare
    # da Azure con un 400, quindi restano qui
    assert "it-IT-IsabellaNeural" in nomi
    assert "it-IT-ElsaNeural" in nomi
    assert "it-IT-DiegoNeural" in nomi
    assert voce_cloud.VOCE_PREDEFINITA in nomi

def test_voce_non_riconosciuta_rifiutata_senza_chiamare_azure():
    assert voce_cloud.voce_valida("it-IT-IsabellaNeural")
    # una voce inventata viene fermata prima della chiamata: l'errore e' leggibile
    # e non costa una richiesta
    assert not voce_cloud.voce_valida("it-XX-InventataNeural")
    assert not voce_cloud.voce_valida("")

def test_sintetizza_senza_configurazione_none(monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    assert voce_cloud.configurato() is False
    with pytest.raises(voce_cloud.ErroreVoce) as e:
        voce_cloud.sintetizza("Ciao", "it-IT-ElsaNeural")
    # 503 e non 502: non e' un guasto, e' una funzione non attivata, e il client
    # usa questo codice per ripiegare sulla voce del browser senza mostrare errori
    assert e.value.stato == 503

def test_testo_troppo_lungo_rifiutato(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    with pytest.raises(voce_cloud.ErroreVoce) as e:
        voce_cloud.sintetizza("a" * (voce_cloud.MAX_CARATTERI + 1), "it-IT-ElsaNeural")
    assert e.value.stato == 400

def test_testo_vuoto_rifiutato(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    with pytest.raises(voce_cloud.ErroreVoce) as e:
        voce_cloud.sintetizza("   ", "it-IT-ElsaNeural")
    assert e.value.stato == 400

def test_la_chiave_messa_a_monte_accende_la_voce(client, tmp_path, monkeypatch):
    """Il giro completo della configurazione preventiva: si scrive il file
    segreto accanto all'app **prima** dell'avvio, e l'app lo trova da sola.

    E' l'unico modo in cui la chiave entra: non c'e' una rotta che la scriva, e
    non c'e' un campo nella pagina. Se questo giro si rompesse, la voce
    tornerebbe meccanica senza che l'utente abbia modo di rimediare.
    """
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)
    (tmp_path / "segreto.sh").write_text(
        "export AZURE_SPEECH_KEY='ChiaveMessaPrima'\n"
        "export AZURE_SPEECH_REGION='italynorth'\n")

    d = client.get("/api/voce/config").get_json()
    assert d["cloud"] is True
    assert d["ascolto"] is True            # la stessa chiave serve al microfono
    # e la chiave continua a non comparire nella risposta
    assert "ChiaveMessaPrima" not in json.dumps(d)

def test_endpoint_config_senza_chiave(client, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    d = client.get("/api/voce/config").get_json()
    assert d["cloud"] is False
    # l'elenco si mostra comunque: serve a capire cosa si attiverebbe
    assert any(v["nome"] == "it-IT-ElsaNeural" for v in d["voci"])
    # la chiave non deve mai comparire nella risposta
    assert "AZURE_SPEECH_KEY" not in json.dumps(d)

def test_elenco_voci_viene_dal_servizio_non_da_un_elenco_scritto(monkeypatch):
    """Le voci offerte devono essere quelle che l'area ha davvero.

    Un elenco scritto a mano offriva due voci "HD" che in italynorth non esistono:
    sceglierle faceva rispondere 400, proprio alla voce presentata come migliore.
    """
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "italynorth")
    monkeypatch.setattr(voce_cloud, "_voci_cache", {"area": None, "quando": 0.0, "elenco": None})
    # risposta di prova: l'area ha Isabella ma non la "HD"
    finta = json.dumps([
        {"ShortName": "it-IT-IsabellaNeural", "Gender": "Female"},
        {"ShortName": "it-IT-DiegoNeural", "Gender": "Male"},
        {"ShortName": "en-US-AvaNeural", "Gender": "Female"},   # altra lingua: fuori
    ]).encode()

    class Risposta:
        def read(self): return finta
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(voce_cloud.urllib.request, "urlopen", lambda *a, **k: Risposta())
    voci = voce_cloud.elenco_voci()
    nomi = [v["nome"] for v in voci]
    assert nomi[0] == voce_cloud.VOCE_PREDEFINITA      # la predefinita resta in testa
    assert "it-IT-IsabellaNeural" in nomi
    assert "it-IT-DiegoNeural" in nomi
    assert not any("en-US" in n for n in nomi)         # solo italiano
    assert not any("DragonHD" in n for n in nomi)      # la "HD" non esiste qui
    # e la voce che l'area non ha viene fermata prima della chiamata
    assert not voce_cloud.voce_valida("it-IT-Isabella:DragonHDLatestNeural")
    assert voce_cloud.voce_valida("it-IT-IsabellaNeural")

def test_elenco_voci_ripiega_se_il_servizio_non_risponde(monkeypatch):
    """Senza risposta dal servizio resta l'elenco scritto a mano: meglio di nessuno."""
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "italynorth")
    monkeypatch.setattr(voce_cloud, "_voci_cache", {"area": None, "quando": 0.0, "elenco": None})

    def esplode(*a, **k):
        raise OSError("rete assente")

    monkeypatch.setattr(voce_cloud.urllib.request, "urlopen", esplode)
    nomi = {v["nome"] for v in voce_cloud.elenco_voci()}
    assert "it-IT-IsabellaNeural" in nomi               # il ripiego c'e'
    assert voce_cloud.voce_valida("it-IT-ElsaNeural")   # e resta utilizzabile

def test_errore_400_suggerisce_di_cambiare_voce(monkeypatch):
    """L'errore non dice solo che e' andata male: dice cosa fare."""
    import urllib.error
    e = urllib.error.HTTPError("u", 400, "Bad Request", {}, None)
    assert "voce" in voce_cloud._spiega_errore(e).lower()

def test_trascrizione_restituisce_il_testo_riconosciuto(monkeypatch):
    _con_chiave(monkeypatch)
    # un WAV finto abbastanza lungo da non essere scartato come silenzio
    finto = b"\x00" * voce_cloud.MIN_AUDIO_BYTE
    monkeypatch.setattr(
        voce_cloud.urllib.request, "urlopen",
        lambda *a, **k: _Ascolto(json.dumps(
            {"RecognitionStatus": "Success", "DisplayText": "aggiungi due chili di farina in dispensa"}
        ).encode()))
    assert voce_cloud.trascrivi(finto) == "aggiungi due chili di farina in dispensa"

def test_trascrizione_manda_wav_16khz_mono(monkeypatch):
    """Il servizio accetta **solo** WAV PCM 16 kHz: l'intestazione deve dirlo.

    Sbagliarla non da' un errore chiaro: il servizio risponde 400 e sembra un
    guasto dell'app.
    """
    _con_chiave(monkeypatch)
    viste = {}

    def cattura(richiesta, **_k):
        viste["headers"] = {c.lower(): v for c, v in richiesta.header_items()}
        viste["url"] = richiesta.full_url
        return _Ascolto(json.dumps({"RecognitionStatus": "Success", "DisplayText": "ciao"}).encode())

    monkeypatch.setattr(voce_cloud.urllib.request, "urlopen", cattura)
    voce_cloud.trascrivi(b"\x00" * voce_cloud.MIN_AUDIO_BYTE)

    assert viste["headers"]["content-type"] == "audio/wav; codecs=audio/pcm; samplerate=16000"
    assert "language=it-IT" in viste["url"]
    assert "stt.speech.microsoft.com" in viste["url"]

def test_trascrizione_senza_parlato_non_e_un_errore(monkeypatch):
    """Silenzio o rumore: il servizio dice NoMatch, che non e' un guasto.

    Se diventasse un errore, il client mostrerebbe un guasto al posto di
    "non ho sentito nulla", e non ripiegherebbe mai sul riconoscimento del
    browser quando serve davvero.
    """
    _con_chiave(monkeypatch)
    monkeypatch.setattr(
        voce_cloud.urllib.request, "urlopen",
        lambda *a, **k: _Ascolto(json.dumps({"RecognitionStatus": "NoMatch"}).encode()))
    assert voce_cloud.trascrivi(b"\x00" * voce_cloud.MIN_AUDIO_BYTE) == ""

def test_trascrizione_audio_troppo_corto_non_chiama_il_servizio(monkeypatch):
    """Un microfono aperto per sbaglio non deve costare una chiamata."""
    _con_chiave(monkeypatch)

    def non_chiamare(*a, **k):
        raise AssertionError("non doveva contattare Azure")

    monkeypatch.setattr(voce_cloud.urllib.request, "urlopen", non_chiamare)
    assert voce_cloud.trascrivi(b"\x00" * 100) == ""

def test_trascrizione_non_configurata_ripiega(monkeypatch):
    """Senza chiave lo stato e' 503: il client sa che puo' usare il browser."""
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", True)
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", "/nonexistent")
    monkeypatch.setattr(voce_cloud, "DATA_DIR", "/nonexistent")
    assert not voce_cloud.configurato()
    with pytest.raises(voce_cloud.ErroreAscolto) as e:
        voce_cloud.trascrivi(b"\x00" * voce_cloud.MIN_AUDIO_BYTE)
    assert e.value.stato == 503

def test_errore_di_ascolto_401_non_riporta_la_risposta(monkeypatch):
    """La spiegazione resta un messaggio per l'utente, senza dettagli della risorsa."""
    import urllib.error
    e = urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
    messaggio = voce_cloud._spiega_errore_ascolto(e)
    assert "chiave" in messaggio.lower() and "401" not in messaggio

def test_la_scheda_voce_e_stata_rimossa(client):
    """Le impostazioni della voce (timbro, voce neurale) non hanno piu' una scheda
    nelle FAQ: il pannello del microfono resta ai comandi soltanto."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="tab-voce"' not in html
    for pezzo in ('id="voice-pick"', 'id="voice-all"', 'id="voice-cloud"',
                  'id="voice-ting"'):
        assert pezzo not in html, pezzo
    # il pannello del microfono resta ai comandi
    inizio = html.index('id="voice"')
    pannello = html[inizio:]
    for pezzo in ('id="voice-text"', 'id="voice-retry"', 'id="voice-heard"'):
        assert pezzo in pannello, pezzo

def test_il_profilo_non_ha_piu_il_riepilogo_ne_capire_i_comandi(client):
    """Dal Profilo sono spariti due blocchi: il «Riepilogo ingredienti» e
    «Capire i comandi» (l'interruttore del modello). Restano i dati del profilo,
    le preferite e il salvataggio dei dati."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="pf-report"' not in html
    assert 'Riepilogo ingredienti' not in html
    assert 'id="voice-llm"' not in html
    assert 'id="voice-llm-block"' not in html
    assert 'id="voice-llm-avviso"' not in html
    assert 'Capire i comandi' not in html
    # quello che resta
    assert 'id="pf-name"' in html
    assert 'id="pf-favorites"' in html
    assert 'id="pf-backup"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    # niente funzioni orfane: rimosso il blocco, si toglie anche il codice
    assert 'function renderReport' not in js
    assert 'function popolaLlm' not in js
    assert 'pf-report' not in js
    assert '#voice-llm' not in js

def test_il_profilo_si_raggiunge_anche_dalle_faq(client):
    """Il Profilo si raggiunge **anche** dalle FAQ, dove sta la stessa specie di
    cose — impostazioni di servizio che si cambiano, non voci da consultare. La
    scheda della Cucina resta: `data-section` filtra la barra, quindi la stessa
    scheda compare in due aree. Il pannello resta `tab-profile`."""
    html = client.get("/static/index.html").get_data(as_text=True)
    # la scheda Profilo e' nell'area FAQ...
    assert 'data-tab="profile" data-section="faq"' in html
    # ...e resta anche in quella della Cucina
    assert 'data-tab="profile" data-section="cucina"' in html
    # il pannello del profilo c'e' ancora, uno solo
    assert html.count('id="tab-profile"') == 1
    # nell'area FAQ vengono FAQ e Profilo, FAQ per prima
    assert 'data-tab="faq" data-section="faq"' in html
    assert html.index('data-tab="faq" data-section="faq"') < html.index('data-tab="profile" data-section="faq"')

def test_l_ordine_delle_categorie_in_home(client):
    """L'ordine delle schede in home e' scelto: Cucina, Appunti, FAQ, TV, GYM,
    Igiene. Si verifica sull'ordine nel documento, non sul testo."""
    html = client.get("/static/index.html").get_data(as_text=True)
    inizio = html.index('class="home-cards"')
    fine = html.index('id="home-oggi"')
    schede = html[inizio:fine]
    ordine = [m for m in re.findall(r'data-section="([^"]+)"', schede)]
    assert ordine == ['cucina', 'progetti', 'faq', 'tv', 'gym', 'igiene'], ordine

def test_gli_errori_del_microfono_portano_a_scrivere(client):
    """Se il browser non puo' ascoltare (rete bloccata, microfono negato), l'unica
    strada e' scrivere: il campo va messo a fuoco, senza farlo cercare."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "#voice-text" in js
    assert "campo.focus()" in js

def test_il_pannello_mostra_delle_domande_da_provare(client):
    """Le domande sono una possibilita' nuova: senza un esempio non si scoprono."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'data-say="che cosa c\'è in dispensa"' in html
    assert 'data-say="quanto sale serve"' in html

def test_endpoint_config_con_chiave_non_espone_la_chiave(client, monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "chiave-segreta-di-prova")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    r = client.get("/api/voce/config")
    assert r.get_json()["cloud"] is True
    # il controllo che conta: la chiave resta sul server, il browser vede solo
    # l'elenco delle voci
    assert b"chiave-segreta-di-prova" not in r.data

def test_endpoint_parla_senza_configurazione_da_503(client, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    r = client.post("/api/voce/parla", json={"text": "Ciao", "voice": "it-IT-ElsaNeural"})
    assert r.status_code == 503

def test_endpoint_parla_restituisce_audio(client, monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    # si sostituisce solo la chiamata di rete: il resto del percorso (validazione,
    # SSML, risposta HTTP) e' quello vero
    def finta(testo, voce, rate=1.0, pitch=0.0, stile=None, timeout=12.0):
        return b"ID3finto"
    monkeypatch.setattr(voce_cloud, "sintetizza", finta)
    r = client.post("/api/voce/parla", json={"text": "Fatto.", "voice": "it-IT-ElsaNeural"})
    assert r.status_code == 200
    assert r.mimetype == "audio/mpeg"
    assert r.data == b"ID3finto"

def test_endpoint_parla_rifiuta_voce_inventata(client, monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    r = client.post("/api/voce/parla", json={"text": "Ciao", "voice": "it-XX-NonEsiste"})
    # 400 e non 500: e' una richiesta sbagliata, non un guasto del server
    assert r.status_code == 400

def test_endpoint_parla_richiede_accesso(anon):
    # la chiave del servizio non deve essere usabile da chi non e' collegato:
    # altrimenti chiunque trovi il link potrebbe consumare il credito
    r = anon.post("/api/voce/parla", json={"text": "Ciao", "voice": "it-IT-ElsaNeural"})
    assert r.status_code == 401
    assert anon.get("/api/voce/config").status_code == 401

def test_endpoint_ascolta_restituisce_il_testo(client, monkeypatch):
    """Il microfono passa dal server: il browser non deve raggiungere nessun
    servizio di ascolto, che è quello che gli si blocca dietro firewall e VPN."""
    _con_chiave(monkeypatch)
    monkeypatch.setattr(voce_cloud, "trascrivi", lambda audio, **k: "metti il latte nella spesa")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 200
    assert r.get_json()["testo"] == "metti il latte nella spesa"

def test_endpoint_ascolta_distingue_il_silenzio_dalla_frase_non_capita(client, monkeypatch):
    """Vuoto vuol dire "non ho sentito nulla", ed è diverso da una frase che non
    è un comando: il client lo dice con parole diverse."""
    _con_chiave(monkeypatch)
    monkeypatch.setattr(voce_cloud, "trascrivi", lambda audio, **k: "")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 200
    assert r.get_json()["testo"] == ""

def test_endpoint_ascolta_senza_chiave_dice_al_client_di_ripiegare(client, monkeypatch):
    """503, non 500: non è un guasto, è una funzione non attivata, e il client
    usa il riconoscimento del browser senza mostrare un errore."""
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", True)
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", "/nonexistent")
    monkeypatch.setattr(voce_cloud, "DATA_DIR", "/nonexistent")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 503

def test_endpoint_ascolta_richiede_accesso(anon):
    # la stessa chiave della sintesi: non deve essere usabile da chi non è collegato
    r = anon.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 401

def test_la_config_dice_al_microfono_di_passare_dal_server(client, monkeypatch):
    """Il client sceglie la strada del microfono in base a `ascolto`: se la chiave
    c'è, registra e manda al server; se non c'è, usa il browser. Sbagliare qui
    riporta il microfono al guasto da firewall che si vuole evitare."""
    _con_chiave(monkeypatch)
    assert client.get("/api/voce/config").get_json()["ascolto"] is True
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", "/nonexistent")
    monkeypatch.setattr(voce_cloud, "DATA_DIR", "/nonexistent")
    assert client.get("/api/voce/config").get_json()["ascolto"] is False

def test_la_sveglia_si_riconosce_all_inizio():
    """Il caso normale: si chiama l'assistente e si dice il comando."""
    svegliato, resto = voice.sveglia("maggiordomo aggiungi il latte in dispensa")
    assert svegliato
    assert resto == "aggiungi il latte in dispensa"

def test_la_sveglia_tollera_i_saluti_e_le_storpiature():
    """Il riconoscimento vocale sbaglia i nomi propri, e "maggiordomo" non e'
    una parola comune: se non si accettano le forme vicine, l'assistente
    sembra sordo proprio mentre lo si chiama."""
    for frase in ("hey maggiordomo metti il sale",
                  "ehi maggiordomo, metti il sale",
                  "ok magiordomo metti il sale",
                  "ciao maggiordomo metti il sale"):
        svegliato, resto = voice.sveglia(frase)
        assert svegliato, frase
        assert resto == "metti il sale", frase

def test_la_sveglia_vale_solo_all_inizio_della_frase():
    """Chi parla d'altro non deve far partire un comando: la sveglia e'
    l'invocazione, non una parola qualsiasi della frase."""
    for frase in ("il maggiordomo prepara la cena",
                  "chiama il maggiordomo",
                  "metti il maggiordomo nella lista"):
        svegliato, _ = voice.sveglia(frase)
        assert not svegliato, frase

def test_hey_gg_accensione_automatica_solo_se_gia_concessa(client):
    """Il microfono si apre da solo solo quando tutte e tre le condizioni ci sono.
    Ognuna da sola non basta, ed e' quello che questo test fissa: se ne cadesse
    una, l'app aprirebbe il microfono senza permesso o contro la volonta'."""
    d = _deve_accendere_js(client, """{
      tutte: deveAccendereDaSolo('1', 'granted', true),
      maiAcceso: deveAccendereDaSolo('0', 'granted', true),
      maiAccesoNulla: deveAccendereDaSolo(null, 'granted', true),
      spentoDallUtente: deveAccendereDaSolo('0', 'granted', true),
      permessoDaChiedere: deveAccendereDaSolo('1', 'prompt', true),
      permessoNegato: deveAccendereDaSolo('1', 'denied', true),
      statoIgnoto: deveAccendereDaSolo('1', '', true),
      senzaChiave: deveAccendereDaSolo('1', 'granted', false)
    }""")
    assert d["tutte"] is True
    for caso in ("maiAcceso", "maiAccesoNulla", "spentoDallUtente",
                 "permessoDaChiedere", "permessoNegato", "statoIgnoto",
                 "senzaChiave"):
        assert d[caso] is False, caso

def test_il_cenno_di_ricevuto_solo_quando_c_e_un_comando(client):
    """Chi dice "Hey GG, metti il latte" aspetta un cenno: senza, fra la frase e
    l'esito passano i secondi della trascrizione e non sa se e' stato sentito.
    Ma il cenno vale **solo** per un comando: chiamare e basta riceve gia' la
    risposta di chiamata ("Sì."), e una frase ignorata non merita risposta,
    altrimenti l'ascolto continuo risponde a tutto e diventa insopportabile."""
    d = _cenno_js(client, """{
      comando: cennoDiRicevuto('esegui'),
      chiamata: cennoDiRicevuto('chiedi'),
      ignorata: cennoDiRicevuto('ignora'),
      niente: cennoDiRicevuto()
    }""")
    assert d["comando"].strip(), "un comando deve avere un cenno"
    assert d["chiamata"] == '', "chiamare e basta riceve gia' la risposta di chiamata"
    assert d["ignorata"] == '', "una frase ignorata non merita risposta"
    assert d["niente"] == ''

def test_la_chiamata_risponde_si(client):
    """Chiamato senza comando, l'assistente risponde "Sì." e basta: e' il
    riscontro breve che l'utente ha chiesto di sentire quando si attiva, prima
    del comando. Prima diceva "Dimmi.", piu' lungo e meno immediato.

    Si esegue la funzione pura, cosi' il test verifica **cosa** risponde, non la
    presenza di una stringa."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "cennoDiChiamata")
    d = _esegui_node(blocco + "\nconsole.log(JSON.stringify(cennoDiChiamata()));")
    assert d == "Sì."
    assert "dimmi" not in d.lower()

def test_hey_gg_ascolto_parte_all_accesso(client):
    """Entrando, l'ascolto parte subito, senza doverlo accendere a mano: il click
    su "Entra" e' il gesto che il browser pretende. Un valore assente e' una
    prima volta, e all'accesso parte; solo uno spegnimento esplicito lo tiene
    spento. Senza la chiave non parte, perche' la trascrizione la farebbe il
    browser e li' l'avvio da solo non e' affidabile."""
    d = _deve_accendere_accesso_js(client, """{
      primaVolta: deveAccendereDopoAccesso(null, true),
      giaAcceso: deveAccendereDopoAccesso('1', true),
      spentoDallUtente: deveAccendereDopoAccesso('0', true),
      senzaChiave: deveAccendereDopoAccesso('1', false),
      senzaChiavePrimaVolta: deveAccendereDopoAccesso(null, false)
    }""")
    assert d["primaVolta"] is True, "all'accesso la prima volta deve partire"
    assert d["giaAcceso"] is True
    assert d["spentoDallUtente"] is False, "chi l'ha spento non se lo ritrova acceso"
    assert d["senzaChiave"] is False
    assert d["senzaChiavePrimaVolta"] is False

def test_hey_gg_sveglia_l_assistente():
    """Il secondo modo di chiamare, "Hey GG". Le forme accettate non sono
    indovinate: sono quelle che il trascrittore di Azure rende davvero, misurate
    sintetizzando la frase. Se si accettasse solo la forma scritta "hey gg",
    l'assistente non risponderebbe mai a chi lo chiama a voce."""
    for frase, comando in (
        ("Ai giorni metti il latte nella spesa", "metti il latte nella spesa"),
        ("E i giorni aggiungi due chili di farina", "aggiungi due chili di farina"),
        ("Ai GG metti il latte", "metti il latte"),
        ("Ehi Gigi, metti il latte", "metti il latte"),
        ("Ok Gigi metti il latte", "metti il latte"),
        ("Ciao Gigi metti il latte", "metti il latte"),
        ("Aigigi metti il latte", "metti il latte"),
        ("Giorni, che cosa c'e' in dispensa", "che cosa c'e' in dispensa"),
        # queste sono uscite da `misura_sveglia.py`, non dalla fantasia: sono le
        # forme che il trascrittore rende per "Hey Gi Gi" e per "Ehi GG"
        ("Ai Gigi, metti il latte", "metti il latte"),
        ("Ciao giorni, metti il latte", "metti il latte"),
        ("E i, maggiordomo, metti il latte", "metti il latte"),
        # dette in fretta, il riconoscitore non sente due "gi": sente una parola
        # sola. "Aigi", "Eiji", "Ai g", "AIG", "Aili Gigi" sono tutte in
        # `misura_sveglia.py`, e senza di loro la chiamata resta senza risposta
        ("Aigi, metti il latte", "metti il latte"),
        ("Eiji, metti il latte", "metti il latte"),
        ("Eigi, metti il latte", "metti il latte"),
        ("Aige, metti il latte", "metti il latte"),
        ("Ai g metti il latte", "metti il latte"),
        ("AIG, metti il latte", "metti il latte"),
        ("Aili Gigi, metti il latte", "metti il latte"),
        ("Egiggi, metti il latte", "metti il latte"),
    ):
        svegliato, resto = voice.sveglia(frase)
        assert svegliato, frase
        assert resto == comando, frase

def test_hey_gg_da_solo_chiama_senza_comando():
    """Chiamato e basta: si risponde "Dimmi." e si aspetta. Il resto vuoto e'
    quello che dice al ciclo di non eseguire nulla."""
    svegliato, resto = voice.sveglia("Ai giorni")
    assert svegliato
    assert resto == ""

def test_hey_gg_non_sveglia_il_discorso_di_casa():
    """L'ancora all'inizio e' cio' che separa un richiamo dal discorso: "il nonno
    Gigi arriva alle otto" non deve accendere l'assistente, altrimenti in cucina
    si eseguono le chiacchiere."""
    for frase in ("il nonno Gigi arriva alle otto",
                  "metti il latte nella spesa",
                  "oggi il tempo e' bello",
                  "il maggiordomo prepara la cena",
                  "chiama Gigi per favore",
                  # forme brevi ("g", "gi", "aig") accettate per la sveglia: qui
                  # non sono all'inizio, e non devono accendere nulla. E' il
                  # confine che rende sicure le forme corte, e va tenuto stretto
                  "giro le pulizie",
                  "gita fuori porta",
                  "giornale sul tavolo",
                  "gesso",
                  "gelato in freezer",
                  "aiuto in cucina",
                  "e i piatti sono pronti"):
        svegliato, _ = voice.sveglia(frase)
        assert not svegliato, frase

def test_hey_gg_vale_anche_scritto(client):
    """La stessa frase vale scritta a mano nel campo di testo, non solo detta:
    un modo solo per tutti e due i canali."""
    r = client.post("/api/voice", json={"text": "Ai giorni metti il latte nella spesa"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["intent"] == "shopping_add"
    assert d["name"] == "latte"

def test_senza_sveglia_il_testo_resta_intatto():
    """Fuori dall'ascolto continuo la sveglia non deve toccare il comando:
    "metti il latte" resta quello che era."""
    svegliato, resto = voice.sveglia("metti il latte nella spesa")
    assert not svegliato
    assert resto == "metti il latte nella spesa"

def test_la_sveglia_sente_anche_quando_il_trascrittore_mette_l_articolo():
    """Il difetto vero visto dal telefono: "Ehi maggiordomo" torna dal
    trascrittore come **"E il maggiordomo"** (misurato con `misura_sveglia.py` su
    Elsa; Isabella e Diego rendono "E i, maggiordomo"), e la sveglia non
    scattava. L'app rispondeva "Non ho eseguito" o taceva, sembrando sorda
    proprio mentre la si chiamava.

    Le forme qui sotto non sono inventate: sono quelle uscite dalla misurazione.
    L'articolo da solo non deve bastare, altrimenti "il maggiordomo prepara la
    cena" tornerebbe a essere un ordine."""
    for frase, comando in (
        ("E il maggiordomo, metti il latte?", "metti il latte"),
        ("E il maggiordomo aggiungi il pane", "aggiungi il pane"),
        ("E il maggiordomo?", ""),
        ("E i, maggiordomo, metti il latte", "metti il latte"),
        ("E la maggiordomo metti il sale", "metti il sale"),
    ):
        svegliato, resto = voice.sveglia(frase)
        assert svegliato, frase
        assert resto == comando, frase
    # e l'articolo senza esordio **non** sveglia: e' il confine che tiene fuori
    # le frasi di casa, dove "il maggiordomo" e' il soggetto, non una chiamata
    for frase in ("Il maggiordomo, metti il latte", "la maggiordomo prepara la cena"):
        svegliato, _ = voice.sveglia(frase)
        assert not svegliato, frase

def test_la_sveglia_si_toglie_anche_dal_comando_scritto(client):
    """Il comando "maggiordomo aggiungi il latte" vale anche scritto a mano nel
    campo di testo, non solo detto a voce: la stessa frase in tutti e due i modi."""
    r = client.post("/api/voice", json={"text": "maggiordomo aggiungi il latte in dispensa"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["intent"] == "pantry_add"
    assert d["name"] == "latte"

def test_l_endpoint_sveglia_non_esegue_il_comando(client):
    """In ascolto continuo si sentono anche le frasi che non c'entrano: l'endpoint
    dice solo se era per l'app. Eseguirlo scriverebbe in dispensa ogni frase
    detta in cucina."""
    r = client.post("/api/voce/sveglia", json={"text": "maggiordomo aggiungi il latte in dispensa"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["sveglia"] is True
    assert d["resto"] == "aggiungi il latte in dispensa"
    # niente e' stato eseguito: la dispensa e' vuota
    assert client.get("/api/pantry").get_json() == []

def test_l_endpoint_sveglia_richiede_accesso(anon):
    r = anon.post("/api/voce/sveglia", json={"text": "maggiordomo aggiungi il latte"})
    assert r.status_code == 401

def test_l_ascolto_dice_se_la_frase_conteneva_la_sveglia(client, monkeypatch):
    """La trascrizione e il riconoscimento della sveglia viaggiano insieme: e' la
    stessa comprensione, e il client non deve indovinare da solo."""
    _con_chiave(monkeypatch)
    monkeypatch.setattr(voce_cloud, "trascrivi", lambda audio, **k: "maggiordomo c'e' il latte?")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 200
    d = r.get_json()
    assert d["sveglia"] is True
    # la punteggiatura non serve a un comando: e' la stessa normalizzazione di
    # `parse`, ed e' il motivo per cui il resto non porta il punto interrogativo
    assert d["resto"] == "c'e' il latte"

def test_l_ascolto_di_una_frase_comune_non_sveglia(client, monkeypatch):
    _con_chiave(monkeypatch)
    monkeypatch.setattr(voce_cloud, "trascrivi", lambda a, **k: "che bella giornata oggi")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.get_json()["sveglia"] is False

def test_la_chiave_si_cerca_anche_nel_secondo_file(tmp_path, monkeypatch):
    """Un `segreto.bat` di Windows copiato accanto al server, senza chiave, non
    deve far ignorare il `segreto.sh` che la chiave ce l'ha: e' il caso di chi
    passa dal PC al server, e la voce tornava meccanica senza motivo."""
    (tmp_path / "segreto.bat").write_text("@echo off\nREM file di Windows, senza chiave\n")
    (tmp_path / "segreto.sh").write_text("export AZURE_SPEECH_KEY='ChiaveNelSecondo'\n")
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "ChiaveNelSecondo"

def test_la_chiave_nel_file_dopo_uno_vuoto(tmp_path, monkeypatch):
    """Stessa cosa dal lato opposto: il primo file c'e' ma non dice niente, e la
    lettura deve proseguire invece di fermarsi."""
    (tmp_path / "segreto.sh").write_text("# solo commenti\n")
    (tmp_path / "segreto.bat").write_text('set "AZURE_SPEECH_KEY=DalBat"\n')
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "DalBat"

def test_l_ascolto_continuo_esiste_e_si_accende_dal_pannello(client):
    """La funzione deve essere raggiungibile: un pulsante nel pannello e il
    ciclo che lo mette in pratica."""
    js = client.get("/static/app.js").get_data(as_text=True)
    html = client.get("/").get_data(as_text=True)
    assert 'id="voice-sempre"' in html
    assert "function avviaAscoltoContinuo()" in js
    assert "function cicloAscoltoContinuo()" in js
    assert "function fermaAscoltoContinuo()" in js

def test_l_ascolto_continuo_non_risente_se_stesso(client):
    """Il difetto che rompe la funzione: mentre l'assistente parla, il microfono
    lo sente, riconosce la propria voce come comando e riparte da solo. La pausa
    `sospeso` e il segnale di "fine parlato" esistono per questo."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "sospeso" in js
    assert "function avvisaFineParlato()" in js
    assert "function riprendiDopoLaVoce(" in js
    # la voce del browser segnala la fine con onend dell'ultima frase
    assert "if (ultima) u.onend = avvisaFineParlato;" in js
    # la voce neurale segnala la fine quando l'audio **termina**, non quando parte
    assert "audio.addEventListener('ended', () => finito(true)" in js
    # e non deve piu' segnalarla all'avvio della riproduzione (il difetto)
    assert "await audio.play();" not in js

def test_la_voce_neurale_avvisa_la_fine_quando_l_audio_finisce(client):
    """Il difetto che incastrava l'ascolto dopo il primo comando.

    `play()` risolve **all'inizio** dell'audio, quindi la promessa di
    `parlaCloud` si chiudeva subito: il segnale di "fine parlato" partiva mentre
    Azure stava ancora parlando, il microfono riprendeva sopra la voce,
    l'assistente si risentiva e il ciclo si bloccava. Si esegue la funzione vera
    con un `Audio` finto ma fedele (`play()` subito, 'ended' dopo) e si guarda
    **quando** la promessa si chiude."""
    ordine = _parlaCloud_e_misura(client)
    # l'audio comincia, e solo dopo l'evento 'ended' la promessa si chiude
    assert ordine.index("play") < ordine.index("ended") < ordine.index("risolta")

def test_le_frasi_della_voce_neurale_si_dicono_in_fila(client):
    """Le frasi non si sovrappongono: la voce neurale suona un audio per volta, e
    in parallelo la seconda mangerebbe la prima. Il segnale di silenzio arriva
    **solo** dopo l'ultima, altrimenti l'ascolto continuo ripartirebbe a meta'
    discorso."""
    ordine = _parla_e_misura(client, "Fatto. Il latte e' in lista.")
    assert ordine.count("FINE-PARLATO") == 1, "un solo segnale di fine, non uno per frase"
    assert ordine.index("fine:suona:Fatto.") < ordine.index("suona:Il latte e' in lista.")
    assert (ordine.index("suona:Il latte e' in lista.")
            < ordine.index("fine:suona:Il latte e' in lista."))
    assert ordine[-1] == "FINE-PARLATO", "il silenzio si segnala dopo l'ultima frase"

def test_l_ascolto_continuo_non_si_incastra(client):
    """Se il browser non dice mai che la voce ha finito, il ciclo deve ripartire
    lo stesso: senza il tetto, l'ascolto resterebbe fermo con l'aria di acceso."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "TETTO_VOCE_MS" in js
    assert "voce.tempoVoce = setTimeout(" in js

def test_chiudere_il_pannello_non_spegne_l_ascolto_continuo(client):
    """Il modo d'uso e' proprio a pannello chiuso - si cucina e si parla - e
    fermare il microfono li' renderebbe la funzione inutile quando serve."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function chiudiVoce()" in js
    inizio = js.index("function chiudiVoce()")
    corpo = js[inizio:inizio + 700]
    assert "ascoltoContinuo.continuo" in corpo

def test_il_pulsante_voce_c_e_su_ogni_pagina(client):
    """Il pulsante del microfono deve restare raggiungibile da ogni area: serve
    proprio quando non si possono usare le mani, e un'area senza pulsante e' una
    parte dell'app da cui la voce sparisce senza che nessuno se ne accorga.

    Si esegue `apriSezione` **vera** con un DOM finto che registra le classi del
    pulsante: un test sulle stringhe non si accorgerebbe se una delle quattro
    aree lo nascondesse."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "apriSezione")
    preludio = """
const classi = {};
function elemento(id) {
  classi[id] = classi[id] || new Set();
  return {
    classList: {
      add(c) { classi[id].add(c); },
      remove(c) { classi[id].delete(c); },
      toggle(c, v) { if (v) classi[id].add(c); else classi[id].delete(c); },
      contains(c) { return classi[id].has(c); },
    },
    dataset: {}, innerHTML: '', textContent: '',
  };
}
const nodi = {};
function $(sel) {
  const id = sel.replace(/^#/, '');
  nodi[id] = nodi[id] || elemento(id);
  return nodi[id];
}
function $$() { return []; }
function switchTab() {}
function avviaProfiloSeServe() {}
function esc(t) { return t; }
const SEZIONI = {
  cucina:   { titolo: 'Cucina',   icona: '/static/icons/icona.svg', prima: 'plan' },
  igiene:   { titolo: 'Igiene',   prima: 'igiene' },
  progetti: { titolo: 'Progetti', prima: 'progetti' },
  faq:      { titolo: 'FAQ',      prima: 'faq' },
};
global.window = { scrollTo() {} };
global.document = { title: '' };
"""
    prove = "\n".join(
        f"apriSezione({nome!r}); esiti[{nome!r}] = !classi['mic'].has('hidden');"
        for nome in ("cucina", "igiene", "progetti", "faq"))
    prova = (preludio + blocco + "\nconst esiti = {};\n" + prove
             + "\nconsole.log(JSON.stringify(esiti));")
    esiti = _esegui_node(prova)
    # il pulsante nacque nascosto (`class="mic hidden"`): se resta `hidden` in
    # un'area, da quell'area la voce non si puo' aprire
    for nome, visibile in esiti.items():
        assert visibile, f"il pulsante voce resta nascosto in {nome}"

def test_la_frase_sentita_si_vede_anche_col_pannello_chiuso(client):
    """Con l'ascolto continuo acceso il pannello e' chiuso, e `#voice-heard` sta
    dentro di esso: la frase trascritta e l'esito non si vedono. Chi parla col
    pannello chiuso vede solo il pulsante colorato, e se l'assistente non risponde
    (ascolto continuo: tace sul discorso di casa) sembra che non abbia sentito.

    `mostraFuori` scrive in una riga **fuori** dal pannello. Si esegue la funzione
    vera con node: a pannello chiuso la riga si vede, a pannello aperto no
    (altrimenti si raddoppierebbe)."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "mostraFuori")
    preludio = """
const stato = { nascosto: true, testo: '', classi: '' };
let pannelloChiuso = true;
function $(sel) {
  if (sel === '#voice-fuori') {
    return {
      set hidden(v) { stato.nascosto = v; }, get hidden() { return stato.nascosto; },
      set textContent(v) { stato.testo = v; }, get textContent() { return stato.testo; },
      set className(v) { stato.classi = v; }, get className() { return stato.classi; },
    };
  }
  return { classList: { contains: () => pannelloChiuso } };
}
"""
    prova = preludio + blocco + """
mostraFuori('Ti ho sentito, dimmi.', 'ok');
const chiuso = { nascosto: stato.nascosto, testo: stato.testo, classi: stato.classi };
pannelloChiuso = false;   // pannello aperto: li' c'e' gia' #voice-heard
mostraFuori('Ho sentito: «metti il latte»', 'ok');
const aperto = { nascosto: stato.nascosto };
console.log(JSON.stringify({ chiuso, aperto }));
"""
    d = _esegui_node(prova)
    assert d["chiuso"]["nascosto"] is False, "col pannello chiuso la riga deve vedersi"
    assert "Ti ho sentito" in d["chiuso"]["testo"]
    assert "ok" in d["chiuso"]["classi"]
    assert d["aperto"]["nascosto"] is True, "col pannello aperto la riga non si raddoppia"

def test_le_frasi_fisse_si_preparano_in_anticipo(client):
    """La latenza che si nota di piu' e' il silenzio dopo aver parlato: ogni
    "Comandi." costava un giro di rete **prima** di sentirsi. Le frasi fisse sono
    sempre le stesse, quindi si scaricano in anticipo, senza riprodurle.

    Si esegue la funzione **vera** con node: deve chiedere al server proprio le
    due frasi fisse, e **non** creare nessun `Audio` (preparare non e' parlare)."""
    js = client.get("/static/app.js").get_data(as_text=True)
    codice = (_estrai_funzione_js(js, "audioCloud")
              + _estrai_funzione_js(js, "preriscaldaFrasiFisse"))
    preludio = """
const CLOUD_CACHE_MAX = 40;
const chieste = [];
let audioCreati = 0;
function voceStato() {}
function voceCloudScelta() { return 'it-IT-IsabellaNeural'; }
let voceCloud = { disponibile: true, maxCaratteri: 600, sentite: new Map() };
global.fetch = (url, opzioni) => {
  chieste.push(JSON.parse(opzioni.body).text);
  return Promise.resolve({ ok: true, blob: () => Promise.resolve({}) });
};
class Audio { constructor() { audioCreati++; } }
"""
    prova = (preludio + codice + """
preriscaldaFrasiFisse();
setTimeout(() => console.log(JSON.stringify({ chieste, audioCreati })), 100);
""")
    d = _esegui_node(prova)
    assert sorted(d["chieste"]) == ["Comandi.", "Sì."], d["chieste"]
    assert d["audioCreati"] == 0, "preparare l'audio non deve farlo suonare"

def test_il_microfono_che_non_risponde_non_blocca_il_ciclo(client):
    """Un'altra causa del "dopo il Si. torna muto": `getUserMedia` puo' non
    risolversi (su Android al secondo giro il permesso c'e' gia', e la promessa
    resta appesa). Senza un limite, il ciclo non parte e il sorvegliante lo
    riavvia solo dopo 25 s.

    Si esegue `ascoltaSulServer` **vera** con un `getUserMedia` che non risponde
    mai: l'esito dev'essere `ritenta`, non un silenzio."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "ascoltaSulServer")
    preludio = """
function registra() {}
function ampiezza() { return 0; }
function wavDaCampioni() { return {}; }
function aSediciKhz(c) { return c; }
function voceStato() {}
function $() { return { classList: { add() {}, remove() {} }, hidden: false }; }
let voce = { registratore: null, attivo: false };
const ASCOLTO_BLOCCO = 4096, ASCOLTO_CAMPIONI = 16000;
const ASCOLTO_FINE_MS = 800, ASCOLTO_ATTESA_MS = 4000, ASCOLTO_MAX_MS = 12000;
const ASCOLTO_SILENZIO = 0.012;
class AudioContextFinto { constructor() { this.state = 'running'; this.sampleRate = 16000; } }
global.window = { AudioContext: AudioContextFinto };
Object.defineProperty(globalThis, 'navigator', {
  value: { mediaDevices: { getUserMedia: () => new Promise(() => {}) } },  // mai risolta
  configurable: true,
});
global.setTimeout = setTimeout;
"""
    prova = preludio + blocco + """
const t0 = Date.now();
const avviato = ascoltaSulServer((d) => {
  console.log(JSON.stringify({ esito: d, ms: Date.now() - t0, avviato }));
  process.exit(0);
});
setTimeout(() => { console.log(JSON.stringify({ esito: null })); process.exit(0); }, 9000);
"""
    d = _esegui_node(prova)
    assert d["esito"] and d["esito"].get("ritenta") is True, d
    assert d["ms"] < 8000, f"ha aspettato troppo: {d['ms']} ms"

def test_il_registro_dice_cosa_fa_l_assistente(client):
    """Il riscontro chiesto: l'assistente deve dire in trasparenza cosa fa. Si
    esegue `registra` **vera**: ogni passo finisce in una riga con l'ora e i
    millisecondi, le righe vecchie si buttano (non cresce all'infinito) e il
    pannello ha il contenitore dove scriverle."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "registra")
    preludio = """
const REGISTRO_MAX = 60;
let registroInizio = Date.now();
const figli = [];
const lista = {
  children: figli,
  get firstChild() { return figli[0]; },
  appendChild(li) { figli.push(li); },
  removeChild(li) { figli.splice(figli.indexOf(li), 1); },
  set scrollTop(v) {}, get scrollTop() { return 0; },
  get scrollHeight() { return 0; },
};
let conteggio = null;
const nodi = { 'voice-registro': lista,
               'voice-registro-n': { set textContent(v) { conteggio = v; } } };
function $(sel) { return nodi[sel.replace(/^#/, '')]; }
global.document = {
  createElement: () => ({
    className: '', children: [],
    appendChild(c) { this.children.push(c); },
  }),
  createTextNode: (t) => ({ testo: t }),
};
"""
    prova = preludio + blocco + """
for (let i = 0; i < 70; i++) registra('passo ' + i);
const righe = lista.children.length;
const testo = lista.children[lista.children.length - 1].children
  .map((c) => c.testo || '').join('');
console.log(JSON.stringify({ righe, conteggio, testo, orario: /\\d\\d:\\d\\d:\\d\\d/.test(lista.children[0].children[0].textContent || '') }));
"""
    d = _esegui_node(prova)
    assert d["righe"] == 60, "il registro non deve crescere all'infinito"
    assert d["conteggio"] == "(60)"
    assert "passo 69" in d["testo"]


# ---------------------------------------------------------------- impegni

def test_voce_programma_un_impegno_con_data_e_ora(client):
    """Un dettato con data e ora crea un impegno vero, non una voce di spesa."""
    domani = (date.today() + timedelta(days=1)).isoformat()
    cmd = voice.parse("ricordami il dentista domani alle 15")
    assert cmd["intent"] == "event_add"
    assert cmd["name"] == "dentista"
    assert cmd["when_date"] == domani
    assert cmd["time"] == "15:00"
    assert cmd["category"] == "salute"

    r = client.post("/api/voice", json={"text": "ricordami il dentista domani alle 15"})
    assert r.status_code == 200
    dati = r.get_json()
    assert dati["intent"] == "event_add"
    assert "calendario" in dati["reload"]

    giorno = client.get(f"/api/appointments?giorno={domani}").get_json()
    titoli = [a["title"] for a in giorno["appointments"]]
    assert "dentista" in titoli


def test_voce_impegno_con_promemoria(client):
    """Il promemoria si dice a voce: "una settimana prima" vale sette giorni."""
    futura = (date.today() + timedelta(days=40)).isoformat()
    cmd = voice.parse(f"ricordami la visita una settimana prima il {futura}")
    assert cmd["intent"] == "event_add"
    assert cmd["reminder_days"] == 7
    assert cmd["when_date"] == futura

    r = client.post("/api/voice",
                    json={"text": f"ricordami la visita una settimana prima il {futura}"})
    assert r.status_code == 200
    giorno = client.get(f"/api/appointments?giorno={futura}").get_json()
    voce = next(a for a in giorno["appointments"] if a["title"] == "visita")
    assert voce["reminder_days"] == 7


def test_voce_impegno_deduce_la_categoria(client):
    """Le parole della frase scelgono la categoria, senza doverla dire."""
    assert voice.parse("fissami la riunione di lavoro domani")["category"] == "lavoro"
    assert voice.parse("ricordami il compleanno di mia figlia domani")["category"] == "famiglia"
    assert voice.parse("ricordami la bolletta domani")["category"] == "casa"
    assert voice.parse("ricordami una cosa qualsiasi domani")["category"] is None


def test_voce_impegno_detto_col_giorno_della_settimana(client):
    """Un giorno della settimana vale il prossimo, non quello passato."""
    cmd = voice.parse("ricordami la riunione giovedì alle 9")
    assert cmd["intent"] == "event_add"
    atteso = voice._prossimo_giorno_settimana(date.today(), 3)
    assert cmd["when_date"] == atteso.isoformat()
    assert cmd["time"] == "09:00"


def test_voce_impegno_non_confonde_dispensa_e_spesa(client):
    """Senza una data vera, "segnami"/"ricordami" restano comandi di sempre."""
    assert voice.parse("segnami il latte")["intent"] == "shopping_add"
    assert voice.parse("ricordami il latte")["intent"] == "shopping_add"
    assert voice.parse("metti il latte domani")["intent"] == "shopping_add"
    assert voice.parse("aggiungi la farina alle 5")["intent"] == "shopping_add"
    # e senza data ne' ora non c'e' niente da programmare
    assert voice.parse("ricordami di chiamare la nonna")["intent"] != "event_add"


def test_voce_impegno_richiede_una_data(client):
    """Una frase senza data non crea un impegno: meglio non capire."""
    for frase in ("ricordami il dentista", "segnami un impegno", "fissami la visita"):
        assert voice.parse(frase)["intent"] != "event_add"


def test_voce_impegno_data_esplicita_con_mese(client):
    """Il "25 dicembre" diventa una data ISO, anche se cade l'anno prossimo."""
    cmd = voice.parse("ricordami di pagare la bolletta il 25 dicembre")
    assert cmd["intent"] == "event_add"
    assert cmd["when_date"][5:] == "12-25"
    assert cmd["category"] == "casa"


def test_la_risposta_di_un_impegno_dice_quando_e_se_avvisa(client):
    """Chi ha parlato deve sapere quando e' stato messo e se il promemoria c'e'."""
    dati = client.post("/api/voice",
                       json={"text": "ricordami il dentista domani"}).get_json()
    assert "domani" in dati["message"]
    assert "Ti avviso" in dati["message"]
    assert dati["appointment_id"] is not None
