"""Misura come il trascrittore rende davvero una frase di sveglia.

Le varianti di "Hey GG" accettate in `voice.py` non sono indovinate: sono quelle
che questo script ha misurato. Sintetizza la frase con la voce neurale, come la
direbbe l'utente, e rilegge cosa torna dal trascrittore.

Serve quando si vuole aggiungere o cambiare un modo di chiamare l'assistente:
si mette la frase scritta fra i `DA_PROVARE`, si esegue, e si copiano in
`_SVEGLIA_GG` solo le forme che escono davvero. Indovinarle significa non essere
mai chiamati, o accendere l'assistente su parole di casa.

Richiede la chiave Azure, come l'app: `AZURE_SPEECH_KEY` e
`AZURE_SPEECH_REGION` nell'ambiente, oppure il solito `segreto.txt` accanto.

    ./.venv/bin/python misura_sveglia.py
"""

import os
import sys

# Le frasi da provare: quelle scritte come le direbbe una persona.
DA_PROVARE = [
    "Hey GG, metti il latte nella spesa",
    "Hey Gi Gi metti il latte",
    "Hey Gigi metti il latte",
    "Gigi metti il latte",
    "Ehi GG metti il latte",
    "Ok GiGi metti il latte",
    "Ciao GG metti il latte",
    "Ehi maggiordomo metti il latte",
    # dette in fretta, i due "gi" si fondono: servono a fissare cosa rende il
    # riconoscitore quando la sveglia e' tutta attaccata
    "Hey Gi metti il latte",
    "Ehi Gi metti il latte",
    "Eigi metti il latte",
    "Aigi metti il latte",
    "Hey G G metti il latte",
    "Ehi G G metti il latte",
]


def _chiave_da_file():
    """Le stesse variabili che legge l'app, se il file c'e'."""
    percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)), "segreto.txt")
    if not os.path.exists(percorso):
        return
    for riga in open(percorso, encoding="utf-8"):
        testo = riga.strip()
        if not testo or testo.startswith("#") or ":" not in testo:
            continue
        nome, valore = testo.split(":", 1)
        nome, valore = nome.strip().lower(), valore.strip()
        if nome in ("chiave", "key") and not os.environ.get("AZURE_SPEECH_KEY"):
            os.environ["AZURE_SPEECH_KEY"] = valore
        elif nome in ("area", "region") and not os.environ.get("AZURE_SPEECH_REGION"):
            os.environ["AZURE_SPEECH_REGION"] = valore


def main():
    _chiave_da_file()
    if not os.environ.get("AZURE_SPEECH_KEY"):
        print("Manca la chiave Azure: senza, non c'e' niente da misurare.")
        return 1
    # La sintesi esce in MP3 per default, ma la trascrizione accetta solo WAV
    # PCM 16 kHz: senza questo, la trascrizione torna vuota e sembra che il
    # servizio non senta, mentre e' solo il formato sbagliato.
    os.environ["AZURE_SPEECH_FORMAT"] = "riff-16khz-16bit-mono-pcm"
    import voce_cloud as voce

    for frase in DA_PROVARE:
        audio = voce.sintetizza(frase, voce.VOCE_PREDEFINITA)
        print(f"{frase!r:42} -> {voce.trascrivi(audio)!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
