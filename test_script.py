"""Script di avvio, Windows e pubblicazione.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_una_area_sbagliata_lo_dice_invece_di_sembrare_un_guasto_di_rete(monkeypatch):
    """Il caso riferito dal desktop: "Servizio vocale non raggiungibile:
    [Errno 11001] getaddrinfo failed". L'indirizzo del servizio contiene l'area
    (`italynorth.tts.speech.microsoft.com`), quindi un refuso **non ha un nome da
    risolvere**: l'errore che ne segue parla di rete e non dice cosa correggere.

    Si prova con un refuso tipico e si guarda che il messaggio nomini l'area
    sbagliata e la variabile da controllare, invece di "getaddrinfo"."""
    import voce_cloud
    monkeypatch.setenv("AZURE_SPEECH_KEY", "chiave-finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "italynorht")   # n e h invertite
    voce_cloud._FILE_LETTI = True   # niente file segreto: comanda l'ambiente
    with pytest.raises(voce_cloud.ErroreVoce) as errore:
        voce_cloud.sintetizza("ciao", "it-IT-ElsaNeural")
    messaggio = str(errore.value)
    assert "italynorht" in messaggio, messaggio
    assert "AZURE_SPEECH_REGION" in messaggio, messaggio
    # le aree vere passano: il controllo non deve fermare l'uso normale
    for area in ("italynorth", "westeurope", "eastus"):
        assert voce_cloud.area_valida(area), area
    for area in ("IT", "italia", "", "italynorht"):
        assert not voce_cloud.area_valida(area), area

def test_avvia_accende_anche_la_sorveglianza():
    """`./avvia.sh` da solo deve bastare: dopo ogni ricreazione del container la
    sorveglianza andava riaccesa a mano ed era il passo che si dimenticava, così
    il link restava a 502. Qui si guarda che l'accensione ci sia, che `stop`/lo
    `stop` di `ferma()` la spenga (altrimenti riavvia il server appena fermato) e
    che il richiamo dal sorvegliante non la riaccenda (ricorsione infinita)."""
    avvia = open(f"{BASE_APP}/avvia.sh", encoding="utf-8").read()
    sorveglia = open(f"{BASE_APP}/sorveglia.sh", encoding="utf-8").read()

    assert "avvia_sorveglianza()" in avvia, "manca l'accensione della sorveglianza"
    assert "avvia_sorveglianza" in avvia.split("avvia() {", 1)[1], \
        "avvia() deve chiamarla, non solo definirla"
    assert "ferma_sorveglianza" in avvia.split("ferma() {", 1)[1], \
        "ferma() deve spegnere la sorveglianza prima del server"
    assert "MAGGIORDOMO_SORVEGLIA_GIRO" in avvia
    assert "MAGGIORDOMO_SORVEGLIA_GIRO" in sorveglia, \
        "il sorvegliante deve esportare il freno prima di richiamare avvia.sh"
    # il freno e' un export, non una semplice menzione
    assert "export MAGGIORDOMO_SORVEGLIA_GIRO=1" in sorveglia
    # e lo script sa accendere la sorveglianza da solo
    assert "sorveglianza|sorveglia)" in avvia

def test_avvio_avvisa_se_l_area_non_esiste():
    """L'avvio diceva "voce neurale Azure attiva" anche con l'area sbagliata: chi
    legge quella riga va a cercare un guasto di rete che non c'e', mentre la
    causa e' un refuso. E' successo davvero: in `segreto.bat` era finita l'area
    "s" (la S della conferma scritta al posto sbagliato).

    Si esegue lo script con un'area inesistente e si guarda che NON dica "attiva"."""
    import os
    import subprocess
    ambiente = dict(os.environ)
    ambiente["AZURE_SPEECH_KEY"] = "chiave-finta"
    ambiente["AZURE_SPEECH_REGION"] = "s"
    esito = subprocess.run(["./avvia.sh", "status"], cwd=BASE_APP,
                           env=ambiente, capture_output=True, text=True)
    uscita = esito.stdout + esito.stderr
    assert "NON attiva" in uscita, uscita
    assert "«s»" in uscita, uscita
    assert "AZURE_SPEECH_REGION" in uscita, uscita

def test_voce_bat_non_accetta_un_area_inventata(client):
    """`voce.bat` scrive `segreto.bat` e chiede l'area a mano: qualunque cosa si
    scriva finiva nel file, anche una lettera sola. Ora rifiuta un'area che non
    esiste e la richiede, cosi' il file non puo' piu' nascere sbagliato.

    Si guarda il file vero: la validazione c'e', e l'elenco e' quello di
    `voce_cloud` (due elenchi diversi divergerebbero)."""
    bat = open(f"{BASE_APP}/windows/voce.bat", encoding="utf-8").read()
    assert "non e' un'area Azure" in bat
    # almeno un'area vera e' nell'elenco di controllo
    assert "italynorth" in bat and "westeurope" in bat
    # e la scrittura del file avviene solo dopo il controllo
    pos_controllo = bat.index("non e' un'area Azure")
    pos_scrittura = bat.index("> \"segreto.bat\"")
    assert pos_controllo < pos_scrittura, "il controllo deve venire prima di salvare"

def test_si_vede_da_quale_file_viene_l_area(monkeypatch, tmp_path):
    """Il caso che fa perdere tempo: si corregge un file e l'errore resta, perche'
    il valore vero arriva da un altro posto. Su Windows `avvia.bat` chiama
    `windows\\segreto.bat`, che imposta l'**ambiente**: da li' in poi
    `segreto.txt` non viene nemmeno guardato.

    Qui si guarda che il valore dica la sua **provenienza** (il file esatto), cosi'
    si sa quale correggere."""
    import importlib
    import voce_cloud
    importlib.reload(voce_cloud)
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    (tmp_path / "segreto.txt").write_text(
        "set \"AZURE_SPEECH_KEY=chiave-finta\"\nset \"AZURE_SPEECH_REGION=s\"\n",
        encoding="utf-8")
    voce_cloud._FILE_LETTI = False
    voce_cloud._ORIGINE.clear()
    voce_cloud.BASE_DIR = str(tmp_path)
    voce_cloud.DATA_DIR = str(tmp_path)

    assert voce_cloud.regione() == "s"
    assert voce_cloud.origine("AZURE_SPEECH_REGION") == str(tmp_path / "segreto.txt")
    # e il messaggio d'errore lo dice, cosi' non si corregge il file sbagliato
    with pytest.raises(voce_cloud.ErroreVoce) as errore:
        voce_cloud._controlla_area()
    assert "letta da" in str(errore.value), str(errore.value)

    # dall'ambiente invece lo dice: e' il caso di avvia.bat su Windows
    importlib.reload(voce_cloud)
    monkeypatch.setenv("AZURE_SPEECH_KEY", "chiave-finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "s")
    voce_cloud._FILE_LETTI = True
    assert voce_cloud.origine("AZURE_SPEECH_REGION") == "ambiente"

def test_la_diagnosi_non_stampa_la_chiave():
    """La diagnostica serve a capire da dove viene un valore sbagliato, e si fa
    con qualcuno che guarda: la chiave **non** deve comparire. Si vedono le prime
    lettere e la lunghezza, che bastano a riconoscere un copia-incolla tronco."""
    import subprocess
    esito = subprocess.run(["./avvia.sh", "diagnosi"], cwd=BASE_APP,
                           capture_output=True, text=True)
    uscita = esito.stdout + esito.stderr
    import voce_cloud
    chiave = voce_cloud.chiave()
    if chiave:
        assert chiave not in uscita, "la diagnosi ha stampato la chiave intera"
    # ma la provenienza si vede
    assert "da:" in uscita
    assert "area valida:" in uscita

def test_ripara_voce_corregge_l_area_senza_toccare_la_chiave(tmp_path):
    """Il caso reale: `windows\\segreto.bat` contiene l'area `s`, la chiave e'
    probabilmente giusta. Il riparatore deve cambiare **solo** la riga dell'area:
    una riga scritta male rovinerebbe la chiave, e la chiave non si recupera.

    Si esegue il riparatore **vero** su file veri, e si controlla che la chiave
    resti identica e che `segreto.txt` — che in questo caso non comanda — non
    venga toccato."""
    import ripara_voce
    (tmp_path / "windows").mkdir()
    chiave = "D58nABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnop"
    bat = tmp_path / "windows" / "segreto.bat"
    bat.write_text(
        '@echo off\nREM Chiave della voce neurale. Generato da voce.bat.\n'
        f'set "AZURE_SPEECH_KEY={chiave}"\nset "AZURE_SPEECH_REGION=s"\n',
        encoding="utf-8")
    txt = tmp_path / "segreto.txt"
    txt.write_text(f"chiave: {chiave}\narea: germanywestcentral\n", encoding="utf-8")

    esito = ripara_voce.ripara(str(tmp_path), area="italynorth")

    assert esito == 0
    dopo = bat.read_text(encoding="utf-8")
    # la chiave e' rimasta identica, e l'area e' corretta
    assert chiave in dopo
    assert 'AZURE_SPEECH_REGION=italynorth' in dopo
    assert 'AZURE_SPEECH_REGION=s' not in dopo
    # segreto.txt non comanda (c'e' il .bat) e non viene toccato
    assert "germanywestcentral" in txt.read_text(encoding="utf-8")

def test_ripara_voce_non_tocca_niente_se_l_area_e_giusta(tmp_path):
    """Se l'area e' gia' valida non si scrive: riscrivere un file che contiene una
    chiave funzionante e' un rischio senza guadagno."""
    import ripara_voce
    bat = tmp_path / "windows"
    bat.mkdir()
    (bat / "segreto.bat").write_text(
        'set "AZURE_SPEECH_KEY=k"\nset "AZURE_SPEECH_REGION=westeurope"\n', encoding="utf-8")
    prima = (bat / "segreto.bat").read_text(encoding="utf-8")

    assert ripara_voce.ripara(str(tmp_path), area="italynorth") == 0
    assert (bat / "segreto.bat").read_text(encoding="utf-8") == prima, \
        "un'area valida non va toccata"

def test_ripara_voce_non_scrive_un_area_inventata(tmp_path):
    """Se l'area non e' valida non si scrive niente: meglio un errore chiaro che
    un file corretto con un altro valore sbagliato."""
    import ripara_voce
    (tmp_path / "windows").mkdir()
    bat = tmp_path / "windows" / "segreto.bat"
    bat.write_text('set "AZURE_SPEECH_KEY=k"\nset "AZURE_SPEECH_REGION=s"\n', encoding="utf-8")
    prima = bat.read_text(encoding="utf-8")

    assert ripara_voce.ripara(str(tmp_path), area="italia") == 1
    assert bat.read_text(encoding="utf-8") == prima

def test_windows_avvia_dietro_il_tunnel(client):
    """Su Windows l'app sta dietro Tailscale Funnel (o Cloudflare, o nginx):
    `avvia.bat` deve dirlo all'app, altrimenti vede l'indirizzo del tunnel al
    posto di quello di chi bussa e il freno ai tentativi conta tutti insieme.

    Dimenticarlo non rompe niente in modo visibile — l'app funziona — quindi si
    scoprirebbe solo dal sintomo sbagliato (qualcuno che aspetta senza motivo)."""
    bat = open(f"{BASE_APP}/windows/avvia.bat", encoding="utf-8").read()
    assert "DIETRO_PROXY=1" in bat, "avvia.bat non dichiara di stare dietro un proxy"
    # e la funzione che lo legge esiste davvero lato server
    app_py = open(f"{BASE_APP}/app.py", encoding="utf-8").read()
    assert "DIETRO_PROXY" in app_py and "ProxyFix" in app_py

def test_verifica_pubblico_controlla_le_tre_cose(client):
    """`verifica-pubblico.bat` e' il controllo da fare quando il tunnel sembra
    attivo ma il telefono non carica: le tre cause si confondono fra loro, e se
    ne dimenticasse una il suo verdetto mentirebbe. Deve guardare il tunnel, se
    l'app risponde, e se `DIETRO_PROXY` e' dichiarato in `avvia.bat`.

    Si guarda il file vero: il lavoro sta nel `.ps1` e il `.bat` lo chiama, per
    la stessa ragione per cui esiste `indirizzo.ps1`."""
    bat = open(f"{BASE_APP}/windows/verifica-pubblico.bat", encoding="utf-8").read()
    ps1 = open(f"{BASE_APP}/windows/verifica-pubblico.ps1", encoding="utf-8").read()
    # il .bat non fa il lavoro: chiama il .ps1 accanto a se'
    assert "verifica-pubblico.ps1" in bat
    # 1. il tunnel: si cerca l'indirizzo https invece di fidarsi del codice di
    # uscita, che cambia fra versioni di Tailscale
    assert "funnel status" in ps1 and "https://" in ps1
    # 2. l'app che risponde
    assert "Invoke-WebRequest" in ps1
    # 3. DIETRO_PROXY dichiarato nel file che comanda davvero
    assert 'set "DIETRO_PROXY=1"' in ps1

def test_avvia_bat_annuncia_il_modello(client):
    """`avvia.bat` deve dire da solo se il modello di casa e' pronto.

    Il sintomo «il modello non capisce» ha tre cause (Ollama spento, modello non
    scaricato, interruttore spento) e l'app le confonde in silenzio: senza un
    controllo all'avvio si crede che Ollama sia configurato mentre l'interruttore
    e' spento. Il lavoro sta in `modello.ps1` (come `indirizzo.ps1`), e il `.bat`
    lo chiama."""
    bat = open(f"{BASE_APP}/windows/avvia.bat", encoding="utf-8").read()
    assert "modello.ps1" in bat, "avvia.bat non annuncia lo stato del modello"

def test_verifica_modello_guarda_le_due_cause(client):
    """`verifica-modello.bat` separa le due cause che danno lo stesso sintomo.

    Deve guardare: se Ollama risponde e se il modello che l'app si aspetta e'
    scaricato. La terza causa di un tempo — l'interruttore in Profilo — non
    esiste piu': la comprensione col modello e' sempre attiva. La configurazione
    si chiede all'app (`comprensione`), non si riscrive nello script: due copie
    della stessa regola divergono, e allora lo stato mente."""
    bat = open(f"{BASE_APP}/windows/verifica-modello.bat", encoding="utf-8").read()
    ps1 = open(f"{BASE_APP}/windows/modello.ps1", encoding="utf-8").read()
    # il .bat non fa il lavoro: chiama il .ps1 accanto a se'
    assert "modello.ps1" in bat
    # 1. Ollama che risponde: l'elenco dei modelli sta in /api/tags, non in /v1
    assert "/api/tags" in ps1
    # 2. il modello atteso: chiesto all'app, non scritto a mano qui
    assert "import comprensione" in ps1
    assert "c.modello()" in ps1
    # l'interruttore non esiste piu': lo script non deve piu' nominarlo
    assert "Capire i comandi" not in ps1
    # e l'invito a scaricare il modello giusto, quando manca
    assert "ollama pull" in ps1

def test_lo_stato_del_modello_si_legge_anche_da_windows(client):
    """`avvia.bat` entra in `windows\\` prima di chiamare `modello.ps1`, quindi il
    processo python eredita quella cartella. Se il controllo non si sposta nella
    cartella dell'app, `import comprensione` fallisce e lo stato del modello
    sembrava illeggibile («Avvia l'app una volta con avvia.bat») proprio quando
    l'utente **stava** usando avvia.bat e tutto era a posto.

    Qui si esegue il comando vero dalla cartella `windows\\` dopo essersi spostati
    in quella dell'app, come fa `Push-Location $App`: e' l'unico modo per
    accorgersi di un difetto di *percorso*, che leggendo il codice non si vede."""
    import subprocess
    ps1 = open(f"{BASE_APP}/windows/modello.ps1", encoding="utf-8").read()
    assert "Push-Location $App" in ps1, (
        "il controllo del modello deve eseguire python dalla cartella dell'app")
    py = os.path.join(BASE_APP, ".venv", "bin", "python")
    if not os.path.exists(py):
        py = sys.executable
    script = (
        "import comprensione as c\n"
        "print(c.base_url())\n"
        "print(c.modello())\n"
        'print("1" if c._e_locale() else "0")\n'
        'print("1" if c.configurato() else "0")\n'
    )
    esito = subprocess.run([py, "-c", script], cwd=BASE_APP,
                           capture_output=True, text=True)
    assert esito.returncode == 0, (
        "il comando di lettura del modello deve funzionare dalla cartella "
        "dell'app: " + esito.stderr)
    assert len(esito.stdout.strip().splitlines()) >= 4

def test_il_comando_pubblica_rifiuta_senza_credenziali():
    """Il push non deve mai partire senza un modo di autenticarsi: senza, git
    chiederebbe l'username a un terminale che non c'e' e il fallimento sembrerebbe
    un problema di rete. Si esegue lo script vero senza token e **senza chiave SSH**
    (il percorso della chiave si punta a un file inesistente), e si guarda che
    rifiuti dicendo cosa serve, invece di tentare un push a vuoto.

    E' il difetto che ha lasciato commit non pubblicati credendo che il token ci
    fosse: la variabile puo' esistere ma essere vuota, ed e' lo stesso."""
    import os
    import subprocess
    ambiente = dict(os.environ)
    for nome in ("GITHUB_TOKEN", "GH_TOKEN", "GIT_SSH_COMMAND"):
        ambiente.pop(nome, None)
    ambiente["MAGGIORDOMO_SSH_CONFIG"] = "/nonexistent/ssh/config"
    esito = subprocess.run(["./avvia.sh", "pubblica"], cwd=BASE_APP,
                           env=ambiente, capture_output=True, text=True)
    assert esito.returncode != 0, "senza credenziali il push non deve riuscire"
    assert "autenticarsi" in esito.stdout.lower()
    # e niente push a vuoto: la URL non deve comparire con credenziali dentro
    assert "@github.com" not in esito.stdout + esito.stderr
