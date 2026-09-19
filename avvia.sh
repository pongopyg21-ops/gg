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
  curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/api/meta" 2>/dev/null
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
    return 0
  fi
  giallo "Processo presente (pid $pid) ma non risponde: prova './avvia.sh restart'."
  return 1
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
  -h|--help|help)
    sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    ;;
  *)
    rosso "Comando sconosciuto: $1"
    echo "Uso: $0 [avvia|stop|restart|status|log|test]"
    exit 2
    ;;
esac