"""Genera l'icona dell'app: bandiera svizzera con cielo celeste.

Crea l'SVG (per il browser) e i PNG (per l'icona sul telefono). I PNG si
costruiscono a mano con zlib e struct: il progetto non ha dipendenze per le
immagini e non vale la pena aggiungerne una per due quadrati e una croce.
"""
import os
import struct
import zlib

CIELO = (79, 179, 232)   # celeste, cielo sereno
BIANCO = (255, 255, 255)

# La croce svizzera: nella bandiera vera le braccia sono larghe 6 e lunghe 20 su
# un quadrato di 32, e la croce sta al centro. Qui le stesse proporzioni su una
# griglia di 64, quindi braccio largo 12 e lungo 40.
LATO, BRACCIO, LUNGO = 64, 12, 40
A = (LATO - LUNGO) // 2          # 12: dove comincia la croce
B = A + LUNGO                    # 52: dove finisce


def dentro(x, y):
    """Vero se il punto cade in una delle due barre della croce."""
    verticale = A <= x < B and (LATO - BRACCIO) // 2 <= y < (LATO + BRACCIO) // 2
    orizzontale = A <= y < B and (LATO - BRACCIO) // 2 <= x < (LATO + BRACCIO) // 2
    return verticale or orizzontale


def scrivi_png(percorso, lato):
    """Un PNG quadrato, scritto a mano: scanline, zlib e i blocchi del formato."""
    def scala(i):
        return (i * LATO) // lato

    righe = []
    for y in range(lato):
        riga = bytearray([0])        # filtro 0 (nessuno), poi RGB per pixel
        for x in range(lato):
            r, g, b = BIANCO if dentro(scala(x), scala(y)) else CIELO
            riga += bytes((r, g, b))
        righe.append(bytes(riga))
    grezzo = b"".join(righe)

    def blocco(tipo, dati):
        return (struct.pack(">I", len(dati)) + tipo + dati
                + struct.pack(">I", zlib.crc32(tipo + dati) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", lato, lato, 8, 2, 0, 0, 0)   # 8 bit, RGB
    with open(percorso, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(blocco(b"IHDR", ihdr))
        f.write(blocco(b"IDAT", zlib.compress(grezzo, 9)))
        f.write(blocco(b"IEND", b""))


SVG = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="Il Maggiordomo">
<!-- La bandiera svizzera, ma col cielo sereno al posto del rosso: la croce
     bianca resta, cambia il campo. E' l'icona dell'app. -->
<rect width="64" height="64" rx="14" fill="#4fb3e8"/>
<rect x="{A}" y="{(LATO - BRACCIO) // 2}" width="{LUNGO}" height="{BRACCIO}" fill="#ffffff"/>
<rect x="{(LATO - BRACCIO) // 2}" y="{A}" width="{BRACCIO}" height="{LUNGO}" fill="#ffffff"/>
</svg>
'''

if __name__ == "__main__":
    D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "icons")
    os.makedirs(D, exist_ok=True)
    with open(os.path.join(D, "icona.svg"), "w") as f:
        f.write(SVG)
    scrivi_png(os.path.join(D, "icona-180.png"), 180)
    scrivi_png(os.path.join(D, "icona-512.png"), 512)
    for nome in sorted(os.listdir(D)):
        print(f"  {nome:20} {os.path.getsize(os.path.join(D, nome)):>7} byte")
