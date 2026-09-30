# Il Maggiordomo in un contenitore, per metterlo su una macchina sempre accesa.
#
# Perche' serve: sul computer di casa l'app gira bene, ma se il computer si
# spegne l'indirizzo smette di rispondere. Su un server (una VPS, un NAS, un
# Raspberry Pi) l'app resta raggiungibile **da ovunque**, e il link non cambia.
#
# L'immagine contiene **solo il codice**: i dati (i database, la chiave Azure)
# non entrano mai qui dentro. Si montano da fuori, cosi' aggiornare l'app non
# tocca il ricettario, e l'immagine si puo' pubblicare senza portarsi dietro
# niente di privato.
#
# Avvio tipico:
#   docker build -t maggiordomo .
#   docker run -d --name maggiordomo --restart unless-stopped \
#     -p 12000:12000 \
#     -v /percorso/dati:/dati \
#     -e AZURE_SPEECH_KEY=... -e AZURE_SPEECH_REGION=... \
#     -e LLM_API_KEY=... \
#     maggiordomo
#
# `--restart unless-stopped` e' il `sorveglia.sh` di questo caso: se l'app cade,
# Docker la riavvia; se la macchina si riavvia, riparte da sola.
#
# Con un tunnel davanti (Tailscale Funnel, Cloudflare, nginx) si aggiunge
# `-e DIETRO_PROXY=1`: senza, il freno ai tentativi di accesso conta tutti su
# un indirizzo solo, perche' vede l'indirizzo del proxy.

FROM python:3.13-slim

# Niente file .pyc e output non bufferizzato: in un contenitore il log deve
# arrivare subito a `docker logs`, non restare in un buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=12000 \
    HOST=0.0.0.0 \
    MAGGIORDOMO_DATA=/dati

WORKDIR /app

# Le dipendenze prima del codice: cosi' un ritocco al codice non rifa' il
# livello (e l'installazione) delle dipendenze a ogni build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py schema.sql seed.py houses.py units.py allergens.py voice.py \
     voce_cloud.py comprensione.py igiene.py faq.py magazzino.py ricette_online.py copie.py \
     dispensa.py crea_icona.py ripristina_password.py ./
COPY static ./static

# I dati stanno in un volume, non nell'immagine: `/dati` e' il punto in cui si
# monta la cartella vera. Senza volume l'app parte lo stesso e crea il ricettario
# di partenza, ma i dati sparirebbero alla ricreazione del contenitore.
RUN mkdir -p /dati
VOLUME ["/dati"]

EXPOSE 12000

CMD ["python", "app.py"]
