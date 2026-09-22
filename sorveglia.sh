#!/usr/bin/env bash
# Tiene su il server: se non risponde, lo riavvia da solo.
#
# Perché serve. L'ambiente ricrea il container fra una conversazione e l'altra —
# e qualche volta anche durante. Non muore solo il processo: cambia l'uptime e
# cambiano i processi, quindi il server avviato con ./avvia.sh sparisce e il link
# pubblico comincia a rispondere 502. Questo giro di controllo riavvia il server
# entro pochi secondi, così la finestra in cui il link non risponde passa da ore
# a secondi.
#
# Quello che NON può fare: quando il container viene ricreato muore anche questo
# sorvegliante, perché è un processo come gli altri. Va riavviato anche lui.
# Non esiste in questa immagine un meccanismo di avvio automatico (niente systemd,
# niente cron, PID 1 è l'agent-server di OpenHands): il riavvio dopo una
# ricreazione del container resta manuale.
#
#   ./sorveglia.sh            avvia la sorveglianza in background
#   ./sorveglia.sh stop       ferma la sorveglianza (il server resta acceso)
#   ./sorveglia.sh status     dice se la sorveglianza è attiva
#   ./sorveglia.sh log        mostra le ultime righe del suo log
#
#   INTERVALLO=10 ./sorveglia.sh    controlla ogni 10 secondi invece di 15

set -uo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-12000}"
INTERVALLO="${INTERVALLO:-15}"
PID_FILE="$BASE_DIR/.sorveglia.pid"
LOCK_FILE="$BASE_DIR/.sorveglia.lock"
LOG_FILE="$BASE_DIR/sorveglia.log"
URL="http://127.0.0.1:$PORT/"

verde() { printf '\033[32m%s\033[0m\n' "$*"; }
giallo() { printf '\033[33m%s\033[0m\n' "$*"; }
rosso() { printf '\033[31m%s\033[0m\n' "$*"; }

# Un processo è nostro solo se gira da questa cartella: il controllo è lo stesso
# di avvia.sh, e serve a non fermare il sorvegliante di un altro progetto.
appartiene_a_noi() {
  local pid="$1"
  [ -n "$pid" ] || return 1
  [ -r "/proc/$pid/cwd" ] || return 1
  [ "$(readlink -f "/proc/$pid/cwd" 2>/dev/null)" = "$BASE_DIR" ]
}

vivo() {
  local pid="$1"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  case "$(ps -o stat= -p "$pid" 2>/dev/null | tr -d ' ')" in
    ""|Z*) return 1 ;;
    *)     return 0 ;;
  esac
}

pid_sorvegliante() {
  local pid
  [ -f "$PID_FILE" ] || return 1
  pid="$(cat "$PID_FILE" 2>/dev/null)"
  vivo "$pid" && appartiene_a_noi "$pid" && printf '%s' "$pid"
}

risponde() {
  curl -sf -o /dev/null --max-time 3 "$URL" 2>/dev/null
}

ferma_server() {
  local pid
  pid="$(pid_sorvegliante)"
  if [ -z "$pid" ]; then
    rm -f "$PID_FILE"
    giallo "La sorveglianza non è attiva."
    return 0
  fi
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
  for _ in $(seq 1 20); do
    vivo "$pid" || break
    sleep 0.25
  done
  vivo "$pid" && kill -KILL "$pid" 2>/dev/null
  rm -f "$PID_FILE"
  verde "Sorveglianza fermata (pid $pid)."
}

# Il giro di controllo. Scrive sul log solo quando fa qualcosa: un log che cresce
# ogni 15 secondi con "tutto a posto" diventa illeggibile proprio quando serve.
sorveglia() {
  echo "$(date '+%F %T') sorveglianza avviata (pid $$), porta $PORT" >>"$LOG_FILE"
  while true; do
    if ! risponde; then
      # due letture consecutive: un singolo buco di rete non deve far ripartire
      # un server che sta soltanto rispondendo piano
      sleep 4
      if ! risponde; then
        echo "$(date '+%F %T') il server non risponde: riavvio" >>"$LOG_FILE"
        # flock: se un 'avvia.sh restart' manuale è già in corso, questo giro
        # salta invece di far partire un secondo server sulla stessa porta
        (
          flock -n 9 || exit 0
          cd "$BASE_DIR" || exit 1
          ./avvia.sh >>"$LOG_FILE" 2>&1
        ) 9>"$LOCK_FILE"
        if risponde; then
          echo "$(date '+%F %T') ripartito" >>"$LOG_FILE"
        else
          echo "$(date '+%F %T') il riavvio non ha funzionato, riprovo al prossimo giro" >>"$LOG_FILE"
        fi
      fi
    fi
    sleep "$INTERVALLO"
  done
}

avvia() {
  local pid
  pid="$(pid_sorvegliante)"
  if [ -n "$pid" ]; then
    verde "La sorveglianza è già attiva (pid $pid)."
    return 0
  fi
  rm -f "$PID_FILE"

  # setsid stacca il sorvegliante dalla shell: senza, morirebbe alla fine del
  # comando come qualunque processo avviato in background da qui
  (
    cd "$BASE_DIR" || exit 1
    setsid "$BASE_DIR/sorveglia.sh" --giro >>"$LOG_FILE" 2>&1 </dev/null &
  )

  for _ in $(seq 1 20); do
    sleep 0.25
    pid="$(pgrep -f "sorveglia.sh --giro" 2>/dev/null | while read -r c; do
             vivo "$c" && appartiene_a_noi "$c" && { printf '%s' "$c"; break; }
           done)"
    [ -n "$pid" ] && break
  done

  if [ -n "$pid" ]; then
    printf '%s' "$pid" >"$PID_FILE"
    verde "Sorveglianza attiva (pid $pid). Controlla ogni ${INTERVALLO}s."
    echo "  log: $LOG_FILE"
    return 0
  fi
  rosso "Non sono riuscito ad avviare la sorveglianza."
  tail -n 10 "$LOG_FILE" 2>/dev/null
  return 1
}

stato() {
  local pid
  pid="$(pid_sorvegliante)"
  if [ -z "$pid" ]; then
    giallo "Sorveglianza non attiva."
    return 1
  fi
  verde "Sorveglianza attiva (pid $pid)."
  if risponde; then
    verde "Il server risponde su $URL"
  else
    giallo "Il server non risponde: la sorveglianza lo riavvierà entro ${INTERVALLO}s."
  fi
}

# Il ramo interno del loop: quando il sorvegliante si riavvia da solo non deve
# riavviarsi all'infinito, quindi entra direttamente nel giro.
if [ "${1:-}" = "--giro" ]; then
  sorveglia
  exit 0
fi

case "${1:-avvia}" in
  avvia|start)  avvia ;;
  stop)         ferma_server ;;
  status|stato) stato ;;
  log|logs)     tail -n "${2:-40}" "$LOG_FILE" ;;
  *)
    rosso "Comando sconosciuto: $1"
    echo "Uso: $0 [avvia|stop|status|log]"
    exit 2
    ;;
esac
