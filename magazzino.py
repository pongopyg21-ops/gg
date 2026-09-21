"""Magazzino: tutto quello che si tiene in casa e non si mangia.

Sapone, bagnoschiuma, rasoi, mensole, quadri, batterie. Niente di tutto questo
entra in una ricetta, quindi il magazzino non centra con la cucina: sta dentro
Progetti, dove vivono le cose da fare e da sistemare.

Perche' e' una sezione a parte e non un secondo elenco della dispensa: la
dispensa si confronta con le ricette (quello che c'e' in casa si scala dal
fabbisogno del piano), il magazzino no. Tenerli nella stessa tabella
costringerebbe la generazione della spesa a filtrarli via a ogni giro, e prima
o poi un detergente finirebbe in una lista di ingredienti.

Due scelte deliberate:

- `quantity` e' la giacenza, `min_quantity` la soglia sotto la quale vale la
  pena ricomprare. Non e' una funzione di automazione: serve a vedere a colpo
  d'occhio cosa sta finendo, che e' il motivo per cui si tiene un magazzino.
- la categoria e il luogo sono testo libero con suggerimenti (catalogo qui
  sotto), non un vincolo: la casa di ognuno ha ripostigli che non si
  prevedono, e rifiutare una voce perche' la categoria non e' in elenco
  sarebbe un ostacolo senza vantaggio.
"""

# ------------------------------------------------------------------ categorie
# L'ordine e' quello di visualizzazione: prima le cose che si consumano e si
# ricomprano, poi quelle che si tengono finche' durano.

CATEGORIE = [
    "Pulizia casa",
    "Igiene personale",
    "Cucina",
    "Ferramenta",
    "Elettricita'",
    "Bricolage",
    "Arredo",
    "Auto",
    "Giardino",
    "Altro",
]

# ------------------------------------------------------------------ luoghi
# Dove sta la cosa. Servono a ritrovarla, che e' meta' del problema di un
# magazzino: senza luogo si sa di averla ma non dove.

LUOGHI = [
    "Ripostiglio",
    "Cantina",
    "Garage",
    "Soffitta",
    "Cucina",
    "Bagno",
    "Camera",
    "Salotto",
    "Balcone",
    "Altro",
]

CATEGORIA_DEFAULT = "Altro"
LUOGO_DEFAULT = "Ripostiglio"


def meta():
    """Catalogo per i menu a tendina: le categorie sono struttura, non dati."""
    return {"categories": CATEGORIE, "places": LUOGHI,
            "default_category": CATEGORIA_DEFAULT, "default_place": LUOGO_DEFAULT}
