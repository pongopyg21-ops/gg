#!/usr/bin/env bash
# Avvia Il Cliente in modo stabile.
#
# L'ambiente può essere azzerato fra una sessione e l'altra: i pacchetti
# installati spariscono e i processi in background vengono terminati. Questo
# script rimette insieme le due cose e verifica che il server risponda davvero,
# invece di dare per scontato che sia partito.
#
# Le dipendenze vivono in una venv dentro il progetto (.venv). /workspace è un
# volume che sopravvive all'azzeramento, quindi la venv resta e reinstalla Flask
# solo la prima volta; se non è creabile si ripiega sui pacchetti di sistema.
#
#   ./avvia.sh            avvia (o riavvia se già in esecuzione)
#   ./avvia.sh stop       ferma il server
#   ./avvia.sh restart    ferma e riavvia
#   ./avvia.sh status     dice se è attivo e su quale porta
#   ./avvia.sh log        mostra le ultime righe del log
#   ./avvia.sh test       esegue i test nella venv del progetto
#   ./avvia.sh pubblica   fa il push su GitHub e verifica che sia arrivato
#   ./avvia.sh nuovachiave  rigenera la chiave SSH per il push
#
# Porta: 12000 per impostazione predefinita (è quella inoltrata dall'host).
# Modificabile con PORT=... ./avvia.sh

set -uo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-12000}"
PID_FILE="$BASE_DIR/.avvia.pid"
LOG_FILE="$BASE_DIR/server.log"
DB_FILE="${CUCINA_DB:-$BASE_DIR/cucina.db}"

PYTHON="${PYTHON:-python3}"

# --- voce neurale ---------------------------------------------------------
# La chiave puo' stare in un file accanto all'app invece che nell'ambiente: e'
# anzi il modo normale, perche' cosi' non va riesportata a ogni avvio. L'app
# quel file lo legge da sola (`voce_cloud`), quindi qui non si legge niente: si
# **chiede** all'app quali valori ha trovato, e si dice il vero.
#
# Perche' non si rilegge il file anche in bash: le forme di file sono piu' d'una
# (`segreto.txt` di testo semplice, `segreto.sh` a script, `segreto.bat` su
# Windows) e riscrivere qui il riconoscimento significherebbe due logiche da
# tenere allineate. Quando divergono, lo stato all'avvio mente: e' proprio il
# caso che questo pezzo di script esiste per evitare. Una sola fonte di verita',
# quella dell'app.
#
# Solo lettura: `voce_cloud.chiave()` e `regione()` non scrivono niente e non
# parlano con la rete. Se l'interprete non c'e' ancora (prima `./avvia.sh` non
# ha preparato la venv), si ripiega sulle sole variabili d'ambiente.

stato_voce() {
  local py="$VENV_PYTHON" esito chiave regione
  [ -x "$py" ] || py="$SYS_PYTHON"
  esito="$(cd "$BASE_DIR" && "$py" -c \
    'import voce_cloud as v; print(v.chiave()); print(v.regione())' 2>/dev/null)"
  chiave="$(printf '%s\n' "$esito" | sed -n '1p')"
  regione="$(printf '%s\n' "$esito" | sed -n '2p')"
  # l'interprete non ha risposto: si guarda l'ambiente, che e' la seconda fonte
  [ -n "$chiave" ] || chiave="${AZURE_SPEECH_KEY:-}"
  [ -n "$regione" ] || regione="${AZURE_SPEECH_REGION:-}"

  if [ -n "$chiave" ] && [ -n "$regione" ]; then
    verde "  voce neurale Azure attiva (area: $regione)"
  elif [ -n "$chiave" ] || [ -n "$regione" ]; then
    giallo "  voce neurale non attiva: servono sia AZURE_SPEECH_KEY sia AZURE_SPEECH_REGION"
  else
    echo "  voce: quella del sistema (per la voce neurale: chiave e area in segreto.txt)"
  fi
}

rosso()  { printf '\033[31m%s\033[0m\n' "$*"; }
verde()  { printf '\033[32m%s\033[0m\n' "$*"; }
giallo() { printf '\033[33m%s\033[0m\n' "$*"; }

# --- stato ---------------------------------------------------------------

# Un processo è nostro solo se gira da questa cartella: "app.py" è un nome
# comune e senza questo controllo si rischierebbe di fermare quello di un altro
# progetto.
appartiene_a_noi() {
  local pid="$1"
  [ -n "$pid" ] || return 1
  [ -r "/proc/$pid/cwd" ] || return 1
  [ "$(readlink -f "/proc/$pid/cwd" 2>/dev/null)" = "$BASE_DIR" ]
}

# Il PID del processo principale. Il reloader di Flask ne genera un secondo con
# la stessa riga di comando: si prende il minore, che è il capofila della
# sessione creata da setsid.
pid_attivo() {
  local pid="" candidato
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null)"
    if vivo "$pid" && appartiene_a_noi "$pid"; then
      printf '%s' "$pid"
      return 0
    fi
  fi
  for candidato in $(pgrep -f "app.py" 2>/dev/null | sort -n); do
    if vivo "$candidato" && appartiene_a_noi "$candidato"; then
      printf '%s' "$candidato"
      return 0
    fi
  done
}

risponde() {
  # Si chiede la pagina, non un'API: con le case separate le API rispondono 401
  # finche' non si e' collegati, e un 401 qui farebbe sembrare morto un server
  # che invece e' vivo e pronto a mostrare la schermata di accesso.
  curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/" 2>/dev/null
}

# "kill -0" riesce anche su uno zombie, che però ha già finito di lavorare: in
# questo ambiente i figli di setsid restano in stato Z perché nessuno li raccoglie.
# Trattarlo come vivo farebbe attendere invano e poi "forzare" un processo già
# morto, quindi si guarda lo stato reale.
vivo() {
  local pid="$1" stato
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  stato="$(ps -o stat= -p "$pid" 2>/dev/null | tr -d ' ')"
  [ -n "$stato" ] || return 1
  # lo stato è "Z", "Zs", "Z+"…: conta la prima lettera
  case "$stato" in
    Z*) return 1 ;;
    *)  return 0 ;;
  esac
}

# --- dipendenze ----------------------------------------------------------
#
# La venv sta dentro il progetto (.venv) e NON in $HOME: solo /workspace è un
# volume che sopravvive all'azzeramento dell'ambiente, mentre $HOME viene
# ricostruito ogni volta. Una venv in $HOME sparirebbe come i pacchetti di
# sistema; una venv nel progetto no, quindi reinstallare Flask diventa un caso
# raro (la primissima volta) invece della norma a ogni conversazione.
#
# Se la venv non si riesce a creare — python3-venv assente, disco pieno — non è
# un problema: si ripiega sui pacchetti di sistema, come prima.

SYS_PYTHON="${PYTHON:-python3}"
VENV_DIR="$BASE_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# La venv è utilizzabile solo se il suo interprete parte davvero. Dopo un cambio
# di versione di Python i collegamenti interni puntano a un file che non c'è più
# e il comando muore: in quel caso va ricreata, non solo riusata.
venv_funzionante() {
  [ -x "$VENV_PYTHON" ] && "$VENV_PYTHON" -c "" 2>/dev/null
}

crea_venv() {
  venv_funzionante && return 0
  giallo "Preparo l'ambiente del progetto in .venv…"
  "$SYS_PYTHON" -m venv "$VENV_DIR" 2>/dev/null || return 1
  venv_funzionante
}

pip_installa() {
  local py="$1"
  if [ -f "$BASE_DIR/requirements.txt" ]; then
    "$py" -m pip install -q -r "$BASE_DIR/requirements.txt"
  else
    "$py" -m pip install -q "flask>=3.0"
  fi
}

prepara_ambiente() {
  # caso normale: la venv c'è già e ha tutto (è il motivo per cui esiste)
  if venv_funzionante && "$VENV_PYTHON" -c "import flask" 2>/dev/null; then
    PYTHON="$VENV_PYTHON"
    return 0
  fi

  # venv assente o incompleta: la si crea e si riempie
  if crea_venv; then
    if "$VENV_PYTHON" -c "import flask" 2>/dev/null \
       || pip_installa "$VENV_PYTHON"; then
      if "$VENV_PYTHON" -c "import flask" 2>/dev/null; then
        verde "Ambiente del progetto pronto (.venv)."
        PYTHON="$VENV_PYTHON"
        return 0
      fi
    fi
    rosso "La venv non riesce a importare Flask: ripiego sul sistema."
  fi

  # ripiego: pacchetti di sistema, il comportamento di prima
  if "$SYS_PYTHON" -c "import flask" 2>/dev/null; then
    PYTHON="$SYS_PYTHON"
    return 0
  fi
  giallo "Flask non è installato (l'ambiente è stato azzerato). Lo installo…"
  pip_installa "$SYS_PYTHON" || {
    rosso "Installazione fallita. Provvedi a mano con: $SYS_PYTHON -m pip install -r requirements.txt"
    return 1
  }
  "$SYS_PYTHON" -c "import flask" 2>/dev/null || {
    rosso "Flask continua a non essere importabile da $SYS_PYTHON."
    return 1
  }
  verde "Flask installato."
  PYTHON="$SYS_PYTHON"
}

# --- azioni --------------------------------------------------------------

ferma() {
  local pid
  pid="$(pid_attivo)"
  if [ -z "$pid" ]; then
    rm -f "$PID_FILE"
    giallo "Nessun server in esecuzione."
    return 0
  fi
  # il segno meno termina tutto il gruppo: così se ne va anche il reloader
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
  for _ in $(seq 1 20); do
    vivo "$pid" || break
    sleep 0.25
  done
  if vivo "$pid"; then
    giallo "Non risponde al TERM, forzo."
    kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
  fi
  rm -f "$PID_FILE"
  verde "Server fermato (pid $pid)."
}

avvia() {
  prepara_ambiente || return 1

  local pid
  pid="$(pid_attivo)"
  if [ -n "$pid" ] && risponde; then
    verde "Il server è già attivo (pid $pid)."
    echo "  http://127.0.0.1:$PORT/"
    return 0
  fi
  if [ -n "$pid" ]; then
    giallo "C'è un processo (pid $pid) ma non risponde: lo riavvio."
    ferma
  fi

  if [ ! -f "$DB_FILE" ]; then
    giallo "Database assente: lo creo con seed.py."
    (cd "$BASE_DIR" && "$PYTHON" seed.py) || {
      rosso "seed.py è fallito."
      return 1
    }
  fi

  # setsid stacca il processo dalla shell: senza, muore alla fine del comando.
  (
    cd "$BASE_DIR" || exit 1
    PORT="$PORT" setsid "$PYTHON" app.py >"$LOG_FILE" 2>&1 </dev/null &
  )

  # il pid vero si legge dopo l'avvio: setsid fa da tramite e non lo restituisce
  for _ in $(seq 1 40); do
    pid="$(pid_attivo)"
    risponde && break
    sleep 0.5
  done

  if [ -n "$pid" ]; then
    printf '%s' "$pid" >"$PID_FILE"
  fi

  if risponde; then
    verde "Server attivo su http://127.0.0.1:$PORT/ (pid ${pid:-?})"
    [ -n "${PUBLIC_URL:-}" ] && echo "  $PUBLIC_URL"
    echo "  log: $LOG_FILE"
    # la voce neurale e' l'unica cosa che si configura fuori dal progetto: dire
    # subito se e' stata letta evita di cercare un problema nell'app quando la
    # causa e' una variabile d'ambiente non passata al server
    stato_voce
    return 0
  fi

  rosso "Il server non risponde su questa porta."
  echo "--- ultime righe di $LOG_FILE ---"
  tail -n 15 "$LOG_FILE" 2>/dev/null
  return 1
}

stato() {
  local pid
  pid="$(pid_attivo)"
  if [ -z "$pid" ]; then
    giallo "Fermo."
    return 1
  fi
  if risponde; then
    verde "Attivo (pid $pid) su http://127.0.0.1:$PORT/"
    stato_voce
    return 0
  fi
  giallo "Processo presente (pid $pid) ma non risponde: prova './avvia.sh restart'."
  return 1
}

# --- pubblicazione su GitHub -------------------------------------------------
# Il push va fatto sul branch `main` — che e' il progetto definitivo — e
# **verificato sul server**: `git fetch` puo' lasciare `origin/main` vecchio, e
# allora un push riuscito sembra fallito (o il contrario), col rischio di credere
# pubblicato un lavoro che non c'e'. Qui si confronta con `ls-remote`, che e' la
# verita' del server.
#
# Due modi per autenticarsi, e si sceglie da solo:
#   1. la **chiave SSH** in `/workspace/ssh/config`, fuori dal repository (quindi
#      non puo' finire in git). E' il modo che ha funzionato quando il segreto
#      `GITHUB_TOKEN` non arrivava al container: la chiave non dipende da un
#      segreto iniettato all'avvio della conversazione.
#   2. il **token** dall'ambiente (`GITHUB_TOKEN`, o `GH_TOKEN`), come ripiego.
#      Non entra negli argomenti ne' nella URL: git non lo vedrebbe in `ps`, ma un
#      errore puo' stampare la URL, e in un log di conversazione resterebbe. Si
#      passa da un `GIT_ASKPASS` temporaneo, che si cancella subito.
# Il token non si legge da `segreto.txt`: quello e' la chiave Azure, e un token di
# scrittura su GitHub non va in un file del progetto.
avvia_ssh() {
  # la config SSH del container, se c'e': la chiave vive fuori da ogni repository.
  # Il percorso si puo' cambiare (`MAGGIORDOMO_SSH_CONFIG`): serve ai test, che
  # devono poter provare il caso "nessuna credenziale" senza fare un push vero.
  local cfg="${MAGGIORDOMO_SSH_CONFIG:-/workspace/ssh/config}"
  [ -f "$cfg" ] && export GIT_SSH_COMMAND="ssh -F $cfg"
}

# I permessi della chiave, rimessi a posto se servono.
#
# La cartella `/workspace` sopravvive alla ricreazione del container, ma i
# **permessi** no: torna con il gruppo scrivibile, e `ssh` rifiuta una chiave
# leggibile da altri con un "UNPROTECTED PRIVATE KEY FILE" che sembra un errore
# di GitHub. Qui si rimettono prima di provare, cosi' il caso non si ripresenta.
sistema_chiave() {
  local cfg="${MAGGIORDOMO_SSH_CONFIG:-/workspace/ssh/config}"
  local dir; dir="$(dirname "$cfg")"
  [ -d "$dir" ] || return 0
  chmod 700 "$dir" 2>/dev/null
  [ -f "$cfg" ] && chmod 600 "$cfg" 2>/dev/null
  [ -f "$dir/deploy_key" ] && chmod 600 "$dir/deploy_key" 2>/dev/null
  return 0
}

# `ssh` non e' nell'immagine di base: senza, la chiave non si puo' usare. Si
# installa al volo (`sudo` non chiede la password) — e' un pacchetto di sistema,
# quindi sparisce a ogni ricreazione e va rimesso. Senza questo, un push
# fallirebbe dicendo "Permission denied" e sembrerebbe colpa della chiave.
assicura_ssh() {
  command -v ssh >/dev/null 2>&1 && return 0
  giallo "ssh non c'e': lo installo (openssh-client)."
  if command -v apt-get >/dev/null 2>&1; then
    sudo -n apt-get update -qq >/dev/null 2>&1
    sudo -n apt-get install -y --no-install-recommends openssh-client >/dev/null 2>&1
  fi
  command -v ssh >/dev/null 2>&1
}

pubblica() {
  local ramo="${2:-main}"
  local token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"

  cd "$BASE_DIR" || return 1
  sistema_chiave
  avvia_ssh
  local locale remoto
  locale="$(git rev-parse HEAD 2>/dev/null)" || { rosso "Non sono in un repository git."; return 1; }

  local err; err="$(mktemp)"
  # con il token si usa `origin` (HTTPS), con la chiave l'indirizzo SSH: cosi' la
  # verifica finale legge dallo stesso posto in cui si e' scritto
  local verso="origin"

  if [ -n "$token" ]; then
    # il token puo' non avere i permessi di scrittura, o essere scaduto: si prova e
    # si riporta l'errore di GitHub invece di attribuirlo al branch
    local ask
    ask="$(mktemp)"; chmod 700 "$ask"
    cat >"$ask" <<'ASKPASS'
#!/bin/sh
case "$1" in
  *[Uu]sername*) printf '%s\n' "x-access-token" ;;
  *) printf '%s\n' "$GITHUB_TOKEN" ;;
esac
ASKPASS
    GIT_ASKPASS="$ask" GIT_TERMINAL_PROMPT=0 git push origin "$ramo" >"$err" 2>&1
    local esito=$?
    rm -f "$ask"
  elif [ -n "${GIT_SSH_COMMAND:-}" ]; then
    if ! assicura_ssh; then
      rm -f "$err"
      rosso "ssh non e' disponibile: non posso usare la chiave."
      return 1
    fi
    # `origin` e' in HTTPS, e con quella la chiave SSH non entra in gioco: si
    # spinge all'indirizzo SSH dello stesso repository, ricavato da `origin` invece
    # che scritto a mano (il repo potrebbe cambiare).
    verso="$(git remote get-url origin | sed -E 's#^https://([^/]+)/#ssh://git@\1/#')"
    git push "$verso" "$ramo:refs/heads/$ramo" >"$err" 2>&1
    local esito=$?
  else
    rm -f "$err"
    rosso "Nessun modo di autenticarsi su GitHub."
    echo "  Serve una delle due:"
    echo "   - una chiave SSH in /workspace/ssh/config (deploy key con scrittura), o"
    echo "   - GITHUB_TOKEN fra i segreti della conversazione."
    return 1
  fi

  if [ "$esito" -ne 0 ]; then
    # l'errore di git puo' contenere la URL con dentro il token: non si stampa
    rm -f "$err"
    rosso "Il push non e' riuscito."
    echo "  (GitHub non ha accettato le credenziali: controlla che la chiave abbia"
    echo "   \"Allow write access\", o che il token sia valido e scrivibile.)"
    return 1
  fi
  rm -f "$err"

  # verifica **sul server**, non in locale: e' l'unico modo di sapere se il push
  # e' arrivato davvero
  remoto="$(git ls-remote "$verso" "refs/heads/$ramo" 2>/dev/null | cut -f1)"
  if [ "$remoto" = "$locale" ]; then
    verde "Pubblicato: $ramo = ${locale:0:7}"
  else
    giallo "Il push e' tornato ok ma il server mostra ${remoto:0:7}: riprova."
    return 1
  fi
}

# Genera una nuova chiave SSH per il push, e stampa la parte pubblica da
# aggiungere su GitHub.
#
# Serve quando la chiave non c'e' piu' (o non e' mai stata autorizzata): si
# rigenera qui, si incolla la pubblica fra le **deploy key** del repository
# (spuntando "Allow write access"), e `./avvia.sh pubblica` funziona. La privata
# resta in `/workspace/ssh`, **fuori da ogni repository**, quindi non puo' finire
# in git.
nuova_chiave() {
  assicura_ssh || { rosso "ssh non e' disponibile: non posso generare la chiave."; return 1; }
  local dir="/workspace/ssh"
  mkdir -p "$dir"
  if [ -f "$dir/deploy_key" ] && [ "${2:-}" != "forza" ]; then
    giallo "Esiste gia' una chiave in $dir/deploy_key."
    echo "  Per rifarla da zero: ./avvia.sh nuovachiave forza"
  else
    ssh-keygen -t ed25519 -N "" -C "openhands-maggiordomo-deploy" -f "$dir/deploy_key" >/dev/null
  fi
  sistema_chiave
  printf 'Host github.com\n  HostName github.com\n  User git\n  IdentityFile %s/deploy_key\n  IdentitiesOnly yes\n  StrictHostKeyChecking accept-new\n' "$dir" > "$dir/config"
  chmod 600 "$dir/config"
  echo
  verde "Chiave pronta. Incolla questa riga su GitHub:"
  echo "  https://github.com/pongopyg21-ops/gg/settings/keys  →  Add deploy key"
  echo "  (spunta \"Allow write access\")"
  echo
  cat "$dir/deploy_key.pub"
  echo
}

# I test girano nella venv del progetto, così vedono le stesse dipendenze del
# server. Il server non serve: i test usano un database temporaneo.
testa() {
  prepara_ambiente || return 1
  if ! "$PYTHON" -c "import pytest" 2>/dev/null; then
    giallo "pytest non c'è: lo installo."
    "$PYTHON" -m pip install -q pytest || return 1
  fi
  (cd "$BASE_DIR" && "$PYTHON" -m pytest test_cucina.py -q)
}

case "${1:-avvia}" in
  avvia|start)   avvia ;;
  stop)          ferma ;;
  restart)       ferma && avvia ;;
  status|stato)  stato ;;
  log|logs)      tail -n "${2:-40}" "$LOG_FILE" ;;
  test|tests)    testa ;;
  pubblica|push) pubblica "$@" ;;
  nuovachiave)   nuova_chiave "$@" ;;
  -h|--help|help)
    sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    ;;
  *)
    rosso "Comando sconosciuto: $1"
    echo "Uso: $0 [avvia|stop|restart|status|log|test|pubblica|nuovachiave]"
    exit 2
    ;;
esac