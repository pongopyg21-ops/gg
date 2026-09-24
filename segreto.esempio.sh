# Copia questo file, chiamalo `segreto.sh`, togli il cancelletto alle due righe
# in fondo e metti i tuoi valori. Poi riavvia l'app.
#
# Perche' cosi': `segreto.sh` e' escluso da git, `avvia.sh` no. La chiave deve
# stare qui, altrimenti finisce su GitHub insieme al codice.
#
# Non serve fare `export` a mano prima di avviare: `voce_cloud.py` legge questo
# file da solo quando l'ambiente non ha gia' la chiave. E' lo stesso meccanismo
# di `segreto.bat` su Windows, e serve perche' un riavvio senza chiave fa tornare
# la voce meccanica senza che si capisca il perche'.

# ============================================================
#  Chiave della voce neurale Azure  (facoltativa)
# ============================================================
#
#  Senza queste righe l'app usa la voce del sistema: funziona lo stesso,
#  semplicemente la voce del browser e' meno bella.
#
#  Dove trovarle, nella pagina della risorsa "Speech" di Azure
#  (portal.azure.com -> la tua risorsa -> Chiavi ed endpoint):
#
#    AZURE_SPEECH_KEY     una delle due chiavi (Chiave 1 o Chiave 2)
#    AZURE_SPEECH_REGION  l'area della risorsa, per esempio westeurope
#
#  L'area si scrive in minuscolo, senza spazi: italynorth, westeurope, eastus.
#  Scritta male, la sintesi non parte e non dice perche'.

# export AZURE_SPEECH_KEY=incolla-qui-la-chiave
# export AZURE_SPEECH_REGION=italynorth
