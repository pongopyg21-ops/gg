"""Popola il database con un ricettario italiano di partenza.

Idempotente: le ricette con un nome già presente vengono saltate.

Uso:  python3 seed.py            (usa CUCINA_DB, default cucina.db)

`semina(percorso)` e' anche la funzione che `app.init_db()` chiama per le case
nuove, che nascono con questo ricettario: agisce su un percorso esplicito e non
passa dall'app, cosi' non dipende dalla casa collegata.
"""
import os
import sqlite3
from contextlib import closing

os.environ.setdefault("CUCINA_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "cucina.db"))

import app as app_module  # noqa: E402
import units  # noqa: E402

FRUTTA = "Frutta e Verdura"
CARNE = "Carne e Pesce"
LATTICINI = "Latticini"
DISPENSA = "Dispensa"
CEREALI = "Pane e Cereali"
BEVANDE = "Bevande"
DOLCI = "Dolci"
SURGELATI = "Surgelati"

RECIPES = [
    {
        "name": "Pasta al pomodoro", "servings": 2, "time_minutes": 20, "difficulty": "facile",
        "instructions": (
            "Metti sul fuoco una pentola capiente d'acqua per la pasta e portala a bollore.\n\n"
            "In una padella larga scalda 2 cucchiai d'olio con lo spicchio d'aglio schiacciato: fallo dorare a fiamma dolce per 2 minuti, senza bruciarlo, altrimenti amareggia.\n\n"
            "Togli l'aglio e versa la passata di pomodoro. Sala, aggiungi qualche foglia di basilico e cuoci 15 minuti a fiamma media, mescolando ogni tanto: il sugo e' pronto quando si e' ristretto e il colore e' piu' scuro.\n\n"
            "Quando l'acqua bolle, sala e lessa la pasta. Scolala al dente tenendo da parte mezzo bicchiere di acqua di cottura.\n\n"
            "Versa la pasta nella padella col sugo, aggiungi l'acqua tenuta da parte e salta 1 minuto: l'amido lega il sugo alla pasta. Completa con il basilico fresco spezzato a mano e servi subito."
        ),
        "items": [
            {"name": "Pasta", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Pomodoro", "quantity": 400, "unit": "g", "category": FRUTTA},
            {"name": "Aglio", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Basilico", "quantity": 10, "unit": "g", "category": FRUTTA},
            {"name": "Sale", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },
    {
        "name": "Spaghetti alla carbonara", "servings": 2, "time_minutes": 25, "difficulty": "media",
        "instructions": (
            "Metti l'acqua per la pasta sul fuoco.\n\n"
            "Taglia il guanciale a strisciette e rosolalo in una padella senza olio: il suo grasso basta. Cuoci a fiamma media finche' e' dorato e croccante fuori ma morbido dentro, poi spegni e lascia la padella da parte.\n\n"
            "In una ciotola sbatti i tuorli con il pecorino grattugiato e abbondante pepe nero macinato al momento. Deve venire una crema densa, non liquida: se serve aggiungi un altro po' di pecorino.\n\n"
            "Lessa gli spaghetti al dente. Scolali tenendo da parte un mestolo di acqua di cottura.\n\n"
            "Versa la pasta nella padella del guanciale (fuori dal fuoco), unisci la crema d'uovo e mescola velocemente. Aggiungi l'acqua di cottura un cucchiaio per volta: il calore della pasta, non la fiamma, deve cuocere l'uovo e trasformarlo in una salsa liscia. Se la padella e' troppo calda l'uovo si rapprende: meglio mescolare fuori dal fuoco. Servi con altro pepe e pecorino."
        ),
        "items": [
            {"name": "Spaghetti", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Guanciale", "quantity": 100, "unit": "g", "category": CARNE},
            {"name": "Uova", "quantity": 2, "unit": "pz", "category": LATTICINI},
            {"name": "Pecorino romano", "quantity": 50, "unit": "g", "category": LATTICINI},
            {"name": "Pepe nero", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },
    {
        "name": "Risotto alla milanese", "servings": 2, "time_minutes": 35, "difficulty": "media",
        "instructions": (
            "Tieni il brodo caldo in una pentola a parte: un risotto freddo si blocca.\n\n"
            "In una casseruola larga scalda meta' del burro con la cipolla tritata finissima e falla appassire a fiamma dolce senza colorirla.\n\n"
            "Versa il riso e tostalo 2 minuti, mescolando: i chicchi devono diventare translucidi ai bordi e scoppiettare. E' il passo che tiene il riso sgranato.\n\n"
            "Sfuma con il vino bianco e lascialo evaporare del tutto.\n\n"
            "Aggiungi il brodo un mestolo per volta, aspettando che il precedente sia assorbito prima di versare il successivo. Mescola spesso. Dopo circa 10 minuti unisci lo zafferano sciolto in un mestolo di brodo.\n\n"
            "Dopo 16-18 minuti il riso e' pronto: deve essere cremoso ma con il chicco ancora al dente. Spegni, manteca con il burro rimasto e il parmigiano, copri e lascia riposare 2 minuti. Servi subito: il risotto non aspetta."
        ),
        "items": [
            {"name": "Riso", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Zafferano", "quantity": 1, "unit": "pz", "category": DISPENSA},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Burro", "quantity": 40, "unit": "g", "category": LATTICINI},
            {"name": "Brodo", "quantity": 800, "unit": "ml", "category": DISPENSA},
            {"name": "Parmigiano", "quantity": 60, "unit": "g", "category": LATTICINI},
            {"name": "Vino bianco", "quantity": 100, "unit": "ml", "category": BEVANDE},
        ],
    },
    {
        "name": "Lasagne alla bolognese", "servings": 4, "time_minutes": 90, "difficulty": "difficile",
        "instructions": (
            "Prepara il ragu': trita sedano, carota e cipolla e soffriggili in olio a fiamma dolce per 5 minuti. Aggiungi il macinato e rosolalo finche' non e' bruno, poi sfuma con mezzo bicchiere di vino e lascia evaporare. Unisci la passata, sala e cuoci a fuoco basso 40 minuti: piu' cuoce, piu' e' buono.\n\n"
            "Prepara la besciamella: sciogli il burro, aggiungi la farina e cuoci 1 minuto, poi versa il latte a filo mescolando con la frusta per non fare grumi. Sala, aggiungi la noce moscata e cuoci finche' non si addensa.\n\n"
            "Preriscalda il forno a 180°C.\n\n"
            "In una teglia stendi un velo di ragu', poi alterna sfoglie di pasta, ragu', besciamella e parmigiano. Ripeti per 4-5 strati, finendo con besciamella e parmigiano abbondante.\n\n"
            "Inforna 40 minuti. Negli ultimi 5 minuti alza la temperatura o accendi il grill per dorare la superficie. Lascia riposare 10 minuti prima di tagliare: le porzioni restano intere."
        ),
        "items": [
            {"name": "Lasagne", "quantity": 250, "unit": "g", "category": CEREALI},
            {"name": "Macinato", "quantity": 400, "unit": "g", "category": CARNE},
            {"name": "Passata di pomodoro", "quantity": 700, "unit": "g", "category": DISPENSA},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Carota", "quantity": 100, "unit": "g", "category": FRUTTA},
            {"name": "Sedano", "quantity": 60, "unit": "g", "category": FRUTTA},
            {"name": "Besciamella", "quantity": 500, "unit": "ml", "category": LATTICINI},
            {"name": "Parmigiano", "quantity": 100, "unit": "g", "category": LATTICINI},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Parmigiana di melanzane", "servings": 4, "time_minutes": 70, "difficulty": "media",
        "instructions": (
            "Taglia le melanzane a fette di circa mezzo centimetro, cospargile di sale grosso e lasciale 30 minuti in uno scolapasta: perdono l'acqua amara. Sciacquale e asciugale bene.\n\n"
            "Grigliale su una piastra ben calda, un paio di minuti per lato, oppure friggile in olio se preferisci la versione tradizionale. Mettile da parte su carta assorbente.\n\n"
            "Preriscalda il forno a 180°C. Prepara un sugo veloce con la passata e un po' di basilico.\n\n"
            "In una teglia alterna un velo di sugo, uno strato di melanzane, passata, mozzarella a cubetti e parmigiano. Ripeti per 3-4 strati e chiudi con parmigiano.\n\n"
            "Inforna 35 minuti, finche' la superficie e' dorata e il sugo sobbolle ai bordi. Fallo riposare 10 minuti prima di servire: si taglia meglio e i sapori si assestano."
        ),
        "items": [
            {"name": "Melanzane", "quantity": 800, "unit": "g", "category": FRUTTA},
            {"name": "Passata di pomodoro", "quantity": 700, "unit": "g", "category": DISPENSA},
            {"name": "Mozzarella", "quantity": 300, "unit": "g", "category": LATTICINI},
            {"name": "Parmigiano", "quantity": 80, "unit": "g", "category": LATTICINI},
            {"name": "Basilico", "quantity": 10, "unit": "g", "category": FRUTTA},
            {"name": "Olio", "quantity": 4, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Farina", "quantity": 50, "unit": "g", "category": DISPENSA},
        ],
    },
    {
        "name": "Minestrone di verdure", "servings": 4, "time_minutes": 50, "difficulty": "facile",
        "instructions": (
            "Trita la cipolla e soffriggila in olio a fiamma dolce in una pentola capiente, finche' non e' trasparente.\n\n"
            "Aggiungi le verdure tagliate a pezzi regolari e falle insaporire 5 minuti, mescolando: prendono gusto prima di bagnarsi.\n\n"
            "Unisci la passata e copri d'acqua o di brodo, due dita sopra le verdure. Sala.\n\n"
            "Cuoci a fuoco medio 30 minuti, poi aggiungi la pasta e prosegui altri 15 minuti: la pasta cuoce direttamente nel brodo e lo addensa.\n\n"
            "Se il minestrone si asciuga troppo, aggiungi acqua calda. Regola di sale, completa con un filo d'olio a crudo e lascia riposare qualche minuto prima di servire: e' ancora meglio il giorno dopo."
        ),
        "items": [
            {"name": "Fagioli", "quantity": 200, "unit": "g", "category": DISPENSA},
            {"name": "Carota", "quantity": 200, "unit": "g", "category": FRUTTA},
            {"name": "Zucchine", "quantity": 200, "unit": "g", "category": FRUTTA},
            {"name": "Patate", "quantity": 300, "unit": "g", "category": FRUTTA},
            {"name": "Sedano", "quantity": 100, "unit": "g", "category": FRUTTA},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Passata di pomodoro", "quantity": 300, "unit": "g", "category": DISPENSA},
            {"name": "Pasta corta", "quantity": 100, "unit": "g", "category": CEREALI},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Pollo al limone", "servings": 2, "time_minutes": 30, "difficulty": "facile",
        "instructions": (
            "Batti leggermente i petti di pollo per renderli di spessore uniforme, salali e infarinateli, scuotendo via l'eccesso.\n\n"
            "Sciogli il burro in una padella larga e rosola il pollo a fiamma media, 3-4 minuti per lato, finche' non e' dorato. Tienilo da parte.\n\n"
            "Nella stessa padella versa il succo dei limoni, raschiando il fondo con un cucchiaio di legno: e' quello che da' sapore alla salsa.\n\n"
            "Rimetti il pollo, abbassa la fiamma, copri e completa la cottura 5 minuti. Il pollo e' pronto quando i succhi sono chiari, non rosa.\n\n"
            "Se la salsa e' troppo liquida, alzala un minuto a fiamma viva. Completa con prezzemolo tritato e qualche scorza di limone grattugiata."
        ),
        "items": [
            {"name": "Petto di pollo", "quantity": 400, "unit": "g", "category": CARNE},
            {"name": "Limone", "quantity": 2, "unit": "pz", "category": FRUTTA},
            {"name": "Farina", "quantity": 30, "unit": "g", "category": DISPENSA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Burro", "quantity": 20, "unit": "g", "category": LATTICINI},
            {"name": "Prezzemolo", "quantity": 1, "unit": "pz", "category": FRUTTA},
        ],
    },
    {
        "name": "Insalata di riso", "servings": 4, "time_minutes": 30, "difficulty": "facile",
        "instructions": (
            "Lessa il riso in acqua salata, scolalo e stendilo su un vassoio o su un canovaccio pulito: raffreddandosi in strato sottile non si appiccica.\n\n"
            "Scola il tonno dall'olio e sbriciolalo. Taglia i pomodorini a meta', la mozzarella a cubetti e snocciola le olive.\n\n"
            "In una ciotola grande unisci riso freddo, tonno, mais, pomodorini, olive e mozzarella.\n\n"
            "Condisci con olio, un pizzico di sale e, se ti piace, una macinata di pepe. Mescola con delicatezza per non rompere la mozzarella.\n\n"
            "Lascia riposare in frigorifero almeno mezz'ora: i sapori si mescolano. Tira fuori 10 minuti prima di servire, il riso freddo di frigo sa di poco."
        ),
        "items": [
            {"name": "Riso", "quantity": 350, "unit": "g", "category": CEREALI},
            {"name": "Tonno", "quantity": 160, "unit": "g", "category": DISPENSA},
            {"name": "Mais", "quantity": 150, "unit": "g", "category": DISPENSA},
            {"name": "Pomodorini", "quantity": 200, "unit": "g", "category": FRUTTA},
            {"name": "Olive", "quantity": 100, "unit": "g", "category": DISPENSA},
            {"name": "Mozzarella", "quantity": 150, "unit": "g", "category": LATTICINI},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Frittata di zucchine", "servings": 2, "time_minutes": 20, "difficulty": "facile",
        "instructions": (
            "Taglia le zucchine a rondelle sottili. Scalda un cucchiaio d'olio in una padella con la cipolla tritata e falle saltare 5 minuti: devono ammorbidirsi ma restare verdi.\n\n"
            "In una ciotola sbatti le uova con il parmigiano, sale e pepe. Unisci le zucchine cotte e mescola.\n\n"
            "Pulisci la padella, scalda l'olio rimasto e versa il composto. Abbassa la fiamma al minimo e cuoci 5-6 minuti: la frittata si rapprende ai bordi.\n\n"
            "Quando il fondo e' dorato, girala. Il modo piu' semplice e' appoggiare un piatto sulla padella e capovolgere, poi far scivolare di nuovo la frittata in padella. Cuoci altri 4 minuti.\n\n"
            "Servila tiepida o fredda: la frittata e' buona anche il giorno dopo."
        ),
        "items": [
            {"name": "Uova", "quantity": 4, "unit": "pz", "category": LATTICINI},
            {"name": "Zucchine", "quantity": 300, "unit": "g", "category": FRUTTA},
            {"name": "Parmigiano", "quantity": 40, "unit": "g", "category": LATTICINI},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Cotoletta alla milanese", "servings": 2, "time_minutes": 25, "difficulty": "facile",
        "instructions": (
            "Batti le fette di carne per assottigliarle leggermente e renderle uniformi, poi salale.\n\n"
            "Sbatti le uova in un piatto fondo con un pizzico di sale. Metti il pangrattato in un altro piatto.\n\n"
            "Passa ogni fetta prima nell'uovo e poi nel pangrattato, premendo bene con le dita: la panatura deve aderire su tutta la superficie e non lasciare punti scoperti.\n\n"
            "Sciogli il burro in una padella larga e cuoci le cotolette a fiamma media, 3-4 minuti per lato. Il burro non deve bruciare: se scurisce troppo, abbassa la fiamma.\n\n"
            "Sono pronte quando la panatura e' dorata e croccante. Servile subito con spicchi di limone da spremere sopra: la crosta deve scrocchiare."
        ),
        "items": [
            {"name": "Fette di vitello", "quantity": 300, "unit": "g", "category": CARNE},
            {"name": "Uova", "quantity": 2, "unit": "pz", "category": LATTICINI},
            {"name": "Pangrattato", "quantity": 100, "unit": "g", "category": CEREALI},
            {"name": "Farina", "quantity": 50, "unit": "g", "category": DISPENSA},
            {"name": "Burro", "quantity": 50, "unit": "g", "category": LATTICINI},
            {"name": "Limone", "quantity": 1, "unit": "pz", "category": FRUTTA},
        ],
    },
    {
        "name": "Orata al forno", "servings": 2, "time_minutes": 35, "difficulty": "facile",
        "instructions": (
            "Preriscalda il forno a 200°C.\n\n"
            "Sbuccia le patate, tagliale a fette sottili e condiscile con olio, sale e un po' di prezzemolo. Disponile in uno strato uniforme sul fondo di una teglia: fanno da letto all'orata e ne raccolgono i succhi.\n\n"
            "Adagia l'orata pulita sulle patate. Condisci con olio, sale, fette di limone e prezzemolo, anche dentro la pancia.\n\n"
            "Inforna 25 minuti. Le patate devono essere tenere e il pesce cotto: la carne si stacca dalla lisca con la forchetta.\n\n"
            "Se le patate sono ancora dure ma il pesce e' pronto, copri il pesce con un foglio di alluminio e prosegui solo per le patate. Servi con il fondo di cottura e altro limone."
        ),
        "items": [
            {"name": "Orata", "quantity": 2, "unit": "pz", "category": CARNE},
            {"name": "Patate", "quantity": 400, "unit": "g", "category": FRUTTA},
            {"name": "Limone", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Prezzemolo", "quantity": 1, "unit": "pz", "category": FRUTTA},
        ],
    },
    {
        "name": "Nigiri di salmone", "servings": 2, "time_minutes": 40, "difficulty": "media",
        "instructions": (
            "Lava il riso sotto l'acqua corrente finche' non esce limpida: serve a togliere l'amido in superficie, altrimenti diventa colloso. Lascialo scolare 10 minuti.\n\n"
            "Cuocilo con una quantita' d'acqua pari al suo volume. Quando bolle, copri e cuoci a fiamma bassa 12 minuti, poi lascia riposare 10 minuti senza aprire.\n\n"
            "Scalda l'aceto di riso con lo zucchero e il sale finche' non sono sciolti, senza portarlo a bollore. Versalo sul riso caldo e mescola con un cucchiaio di legno, con movimenti che non schiacciano i chicchi. Lascia intiepidire.\n\n"
            "Con le mani leggermente bagnate, forma delle palline ovali di riso compatte ma non schiacciate.\n\n"
            "Taglia il salmone a fette sottili con un coltello affilato, in diagonale. Appoggia una fetta su ogni pallina di riso e premi appena. Servi subito, con salsa di soia a parte."
        ),
        "items": [
            {"name": "Riso", "quantity": 200, "unit": "g", "category": CEREALI},
            {"name": "Salmone", "quantity": 200, "unit": "g", "category": CARNE},
            {"name": "Aceto di riso", "quantity": 30, "unit": "ml", "category": DISPENSA},
            {"name": "Zucchero", "quantity": 10, "unit": "g", "category": DISPENSA},
            {"name": "Sale", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
            {"name": "Wasabi", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
            {"name": "Salsa di soia", "quantity": 30, "unit": "ml", "category": DISPENSA},
        ],
    },
    {
        "name": "Gnocchi al ragù", "servings": 4, "time_minutes": 60, "difficulty": "media",
        "instructions": (
            "Prepara il ragu': trita cipolla, carota e sedano e soffriggili in olio a fiamma dolce 5 minuti. Aggiungi il macinato, rosolalo bene, poi unisci la passata e sala.\n\n"
            "Cuoci a fuoco basso 40 minuti, mescolando ogni tanto. Il ragu' e' pronto quando non sa piu' di pomodoro crudo e il grasso si e' separato in superficie.\n\n"
            "Porta a bollore l'acqua per gli gnocchi e salala.\n\n"
            "Butta gli gnocchi e scolali appena risalgono a galla: cuociono in 2-3 minuti e, se li lasci troppo, diventano gommosi.\n\n"
            "Condiscili con il ragu' e una spolverata di parmigiano. Saltali un momento in padella col sugo, cosi' si insaporiscono."
        ),
        "items": [
            {"name": "Gnocchi", "quantity": 800, "unit": "g", "category": CEREALI},
            {"name": "Macinato", "quantity": 400, "unit": "g", "category": CARNE},
            {"name": "Passata di pomodoro", "quantity": 600, "unit": "g", "category": DISPENSA},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Carota", "quantity": 100, "unit": "g", "category": FRUTTA},
            {"name": "Sedano", "quantity": 60, "unit": "g", "category": FRUTTA},
            {"name": "Parmigiano", "quantity": 60, "unit": "g", "category": LATTICINI},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Croque madame", "servings": 2, "time_minutes": 30, "difficulty": "facile",
        "instructions": (
            "Prepara la besciamella: sciogli il burro, unisci la farina e cuoci 1 minuto, poi versa il latte a filo mescolando con la frusta. Sala, aggiungi la noce moscata e cuoci finche' non si addensa.\n\n"
            "Preriscalda il forno a 200°C.\n\n"
            "Tosta leggermente le fette di pane: cosi' non si inzuppano di besciamella. Spalma un po' di besciamella su due fette, aggiungi prosciutto e formaggio, e chiudi i sandwich.\n\n"
            "Copri la superficie con altra besciamella e una manciata di formaggio grattugiato. Inforna 15 minuti, finche' la superficie e' dorata e sobbolle.\n\n"
            "Nel frattempo cuoci un uovo al tegamino in un padellino con un filo d'olio: l'albume deve essere rappreso e il tuorlo liquido. Adagialo sopra il sandwich appena sfornato e servi subito."
        ),
        "items": [
            {"name": "Pane in cassetta", "quantity": 4, "unit": "fetta", "category": CEREALI},
            {"name": "Prosciutto cotto", "quantity": 120, "unit": "g", "category": CARNE},
            {"name": "Gruyere", "quantity": 120, "unit": "g", "category": LATTICINI},
            {"name": "Latte", "quantity": 250, "unit": "ml", "category": LATTICINI},
            {"name": "Burro", "quantity": 30, "unit": "g", "category": LATTICINI},
            {"name": "Farina", "quantity": 30, "unit": "g", "category": DISPENSA},
            {"name": "Uova", "quantity": 2, "unit": "pz", "category": LATTICINI},
            {"name": "Noce moscata", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },
    {
        "name": "Pad thai", "servings": 2, "time_minutes": 35, "difficulty": "media",
        "instructions": (
            "Metti i noodles di riso in una ciotola e coprili di acqua calda (non bollente). Lasciali 15-20 minuti, finche' sono flessibili ma ancora consistenti: scolali e tienili da parte. Se li ammolli troppo si sfaldano in padella.\n\n"
            "Prepara la salsa mescolando salsa di soia, succo di lime, zucchero e, se lo hai, un cucchiaio di salsa di pesce.\n\n"
            "Scalda il wok o una padella larga a fiamma alta con l'olio. Salta l'aglio tritato pochi secondi, poi aggiungi i gamberi e cuocili 2 minuti: devono diventare rosa.\n\n"
            "Spingi tutto da un lato e versa le uova sbattute: strapazzale, poi mescola col resto.\n\n"
            "Aggiungi i noodles e la salsa, saltando velocemente 2 minuti. Completa con i germogli di soia, le arachidi tritate e il peperoncino. Servi con spicchi di lime: il pad thai va mangiato subito."
        ),
        "items": [
            {"name": "Noodles di riso", "quantity": 200, "unit": "g", "category": CEREALI},
            {"name": "Gamberi", "quantity": 200, "unit": "g", "category": CARNE},
            {"name": "Uova", "quantity": 2, "unit": "pz", "category": LATTICINI},
            {"name": "Germogli di soia", "quantity": 100, "unit": "g", "category": FRUTTA},
            {"name": "Salsa di soia", "quantity": 30, "unit": "ml", "category": DISPENSA},
            {"name": "Arachidi", "quantity": 40, "unit": "g", "category": DISPENSA},
            {"name": "Lime", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Aglio", "quantity": 2, "unit": "pz", "category": FRUTTA},
            {"name": "Peperoncino", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Spaghetti alle vongole", "servings": 2, "time_minutes": 30, "difficulty": "media",
        "instructions": (
            "Metti le vongole in acqua salata per un'ora, cosi' spurgono la sabbia. Sciacquale bene sotto l'acqua corrente.\n\n"
            "Metti l'acqua per la pasta sul fuoco.\n\n"
            "In una padella larga scalda l'olio con l'aglio schiacciato e il peperoncino. Aggiungi le vongole, sfuma con il vino bianco e copri: in pochi minuti si aprono. Scarta quelle che restano chiuse.\n\n"
            "Lessa gli spaghetti al dente e scolali tenendo un po' di acqua di cottura.\n\n"
            "Versa la pasta nella padella con le vongole, aggiungi un mestolo di acqua di cottura e salta 1 minuto: il sugo deve velare la pasta. Completa con prezzemolo tritato e servi, senza formaggio."
        ),
        "items": [
            {"name": "Spaghetti", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Vongole", "quantity": 600, "unit": "g", "category": CARNE},
            {"name": "Aglio", "quantity": 2, "unit": "pz", "category": FRUTTA},
            {"name": "Prezzemolo", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Peperoncino", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Vino bianco", "quantity": 100, "unit": "ml", "category": BEVANDE},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Fish & chips al forno", "servings": 2, "time_minutes": 45, "difficulty": "facile",
        "instructions": (
            "Preriscalda il forno a 220°C.\n\n"
            "Taglia le patate a bastoncini, asciugale bene con un canovaccio e condiscile con olio, sale e pepe. Stendile in un solo strato su una teglia: se si sovrappongono si stufano invece di dorarsi.\n\n"
            "Inforna le patate 20 minuti, girandole a meta' cottura.\n\n"
            "Nel frattempo prepara tre piatti: farina, uova sbattute, pangrattato. Passa i filetti di merluzzo in quest'ordine, premendo bene la panatura.\n\n"
            "Sfila la teglia, adagia il pesce accanto alle patate, condisci con un filo d'olio e prosegui la cottura 20 minuti, finche' la panatura e' dorata e croccante. Servi con limone e, se piace, maionese."
        ),
        "items": [
            {"name": "Merluzzo", "quantity": 400, "unit": "g", "category": CARNE},
            {"name": "Patate", "quantity": 500, "unit": "g", "category": FRUTTA},
            {"name": "Farina", "quantity": 50, "unit": "g", "category": DISPENSA},
            {"name": "Pangrattato", "quantity": 80, "unit": "g", "category": CEREALI},
            {"name": "Uova", "quantity": 1, "unit": "pz", "category": LATTICINI},
            {"name": "Limone", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Seppia impanata al forno", "servings": 2, "time_minutes": 40, "difficulty": "facile",
        "instructions": (
            "Pulisci le seppie: togli la penna trasparente, le interiora e gli occhi, sciacquale bene. Tagliale ad anelli spessi o a falde, a seconda della grandezza.\n\n"
            "Preriscalda il forno a 200°C e ungi una teglia con l'olio.\n\n"
            "In una ciotola sbatti le uova con sale e prezzemolo tritato. Metti il pangrattato in un piatto.\n\n"
            "Passa le seppie prima nell'uovo e poi nel pangrattato, premendo per farlo aderire. Disponile sulla teglia senza sovrapporle.\n\n"
            "Inforna 20 minuti, girandole a meta' cottura. Sono pronte quando la panatura e' dorata: se le cuoci troppo diventano dure come gomma. Servi con limone."
        ),
        "items": [
            {"name": "Seppia", "quantity": 500, "unit": "g", "category": CARNE},
            {"name": "Pangrattato", "quantity": 120, "unit": "g", "category": CEREALI},
            {"name": "Uova", "quantity": 2, "unit": "pz", "category": LATTICINI},
            {"name": "Farina", "quantity": 40, "unit": "g", "category": DISPENSA},
            {"name": "Prezzemolo", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Limone", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Calamarata", "servings": 4, "time_minutes": 40, "difficulty": "media",
        "instructions": (
            "Pulisci i calamari, tagliali a rondelle e tieni da parte i tentacoli.\n\n"
            "In una padella larga scalda l'olio con l'aglio e il peperoncino. Aggiungi i calamari e saltali 2 minuti a fiamma viva, poi sfuma con il vino bianco.\n\n"
            "Quando il vino e' evaporato, unisci la passata, sala e cuoci 20 minuti a fiamma dolce: i calamari diventano teneri.\n\n"
            "Lessa la calamarata in acqua salata, tenendola al dente.\n\n"
            "Scolala e versala nella padella col sugo, salta 1 minuto per farla insaporire. Completa con prezzemolo tritato e servi. Se il sugo e' troppo denso, allunga con un po' di acqua di cottura."
        ),
        "items": [
            {"name": "Calamarata", "quantity": 400, "unit": "g", "category": CEREALI},
            {"name": "Calamari", "quantity": 500, "unit": "g", "category": CARNE},
            {"name": "Passata di pomodoro", "quantity": 400, "unit": "g", "category": DISPENSA},
            {"name": "Aglio", "quantity": 2, "unit": "pz", "category": FRUTTA},
            {"name": "Vino bianco", "quantity": 100, "unit": "ml", "category": BEVANDE},
            {"name": "Peperoncino", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Prezzemolo", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Gnocchi alla sorrentina", "servings": 4, "time_minutes": 40, "difficulty": "facile",
        "instructions": (
            "Prepara il sugo: scalda l'olio con l'aglio, aggiungi la passata, sala e cuoci 15 minuti a fiamma dolce. Aggiungi qualche foglia di basilico alla fine.\n\n"
            "Porta a bollore l'acqua e lessa gli gnocchi: sono pronti appena risalgono a galla, in 2-3 minuti.\n\n"
            "Scolali e condiscili con il sugo e il basilico.\n\n"
            "Preriscalda il forno a 200°C. Trasferisci gli gnocchi in una teglia, distribuisci sopra la mozzarella a cubetti e il parmigiano.\n\n"
            "Gratina 10-15 minuti, finche' il formaggio e' sciolto e dorato in superficie. Servi subito, quando la mozzarella fila."
        ),
        "items": [
            {"name": "Gnocchi", "quantity": 800, "unit": "g", "category": CEREALI},
            {"name": "Passata di pomodoro", "quantity": 500, "unit": "g", "category": DISPENSA},
            {"name": "Mozzarella", "quantity": 300, "unit": "g", "category": LATTICINI},
            {"name": "Parmigiano", "quantity": 60, "unit": "g", "category": LATTICINI},
            {"name": "Basilico", "quantity": 10, "unit": "g", "category": FRUTTA},
            {"name": "Aglio", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Spaghetti aglio olio e peperoncino", "servings": 2, "time_minutes": 15, "difficulty": "facile",
        "instructions": (
            "Metti l'acqua per la pasta sul fuoco e salala.\n\n"
            "In una padella larga versa l'olio e aggiungi l'aglio in camicia (schiacciato con il palmo, senza sbucciarlo del tutto) e il peperoncino spezzato.\n\n"
            "Scalda a fiamma molto bassa per 3-4 minuti: l'aglio deve dorare lentamente e profumare l'olio, mai bruciare, altrimenti diventa amaro. Togli l'aglio quando e' biondo.\n\n"
            "Lessa gli spaghetti al dente e scolali tenendo un mestolo di acqua di cottura.\n\n"
            "Versa la pasta nella padella, aggiungi l'acqua di cottura e salta 1 minuto a fiamma viva: l'amido emulsiona l'olio e crea una salsina. Completa con prezzemolo tritato e servi subito."
        ),
        "items": [
            {"name": "Spaghetti", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Aglio", "quantity": 3, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 4, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Peperoncino", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Prezzemolo", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Sale", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },
    {
        "name": "Frittata di spaghetti", "servings": 4, "time_minutes": 25, "difficulty": "facile",
        "instructions": (
            "Lessa gli spaghetti in acqua salata e scolali al dente.\n\n"
            "In una ciotola capiente sbatti le uova con il parmigiano, sale e pepe. Unisci gli spaghetti e mescola bene, cosi' ogni filo si ricopre d'uovo.\n\n"
            "Scalda l'olio in una padella antiaderente di media grandezza.\n\n"
            "Versa il composto e schiaccia con il dorso di un cucchiaio per compattarlo e livellarlo: una frittata spessa si cuoce male al centro.\n\n"
            "Cuoci a fiamma dolce 6-7 minuti, finche' il fondo e' dorato. Girala con l'aiuto di un piatto e cuoci altri 5 minuti. Servila tiepida o fredda, tagliata a spicchi."
        ),
        "items": [
            {"name": "Spaghetti", "quantity": 250, "unit": "g", "category": CEREALI},
            {"name": "Uova", "quantity": 6, "unit": "pz", "category": LATTICINI},
            {"name": "Parmigiano", "quantity": 60, "unit": "g", "category": LATTICINI},
            {"name": "Pepe nero", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Sale", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },
    {
        "name": "Tagliatelle al ragù bianco", "servings": 4, "time_minutes": 60, "difficulty": "media",
        "instructions": (
            "Trita finemente cipolla, carota e sedano e soffriggili in olio a fiamma dolce 5 minuti con il rosmarino.\n\n"
            "Aggiungi il macinato e fallo dorare bene, mescolando e sgranandolo con un cucchiaio: deve perdere il rosa e prendere colore.\n\n"
            "Sfuma con il vino bianco e lascia evaporare del tutto, poi unisci un mestolo di brodo e sala.\n\n"
            "Cuoci a fuoco basso 40 minuti, aggiungendo altro brodo se si asciuga: il ragu' bianco deve restare umido, non asciutto.\n\n"
            "Lessa le tagliatelle al dente e condiscile con il ragu' e una spolverata di parmigiano. Il ragu' bianco e' delicato: non coprirlo con troppo formaggio."
        ),
        "items": [
            {"name": "Tagliatelle", "quantity": 320, "unit": "g", "category": CEREALI},
            {"name": "Macinato", "quantity": 400, "unit": "g", "category": CARNE},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Carota", "quantity": 100, "unit": "g", "category": FRUTTA},
            {"name": "Sedano", "quantity": 60, "unit": "g", "category": FRUTTA},
            {"name": "Vino bianco", "quantity": 150, "unit": "ml", "category": BEVANDE},
            {"name": "Brodo", "quantity": 200, "unit": "ml", "category": DISPENSA},
            {"name": "Rosmarino", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Parmigiano", "quantity": 60, "unit": "g", "category": LATTICINI},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Pasta con crema di peperoni", "servings": 2, "time_minutes": 30, "difficulty": "facile",
        "instructions": (
            "Arrostisci i peperoni: mettili interi sotto il grill del forno o sulla fiamma, girandoli, finche' la pelle e' nera e gonfia. Chiudili in un sacchetto o sotto una ciotola 10 minuti: con il vapore la pelle si stacca da sola.\n\n"
            "Pelali, togli i semi e i filamenti bianchi, poi frullali con la panna e un filo d'olio fino a ottenere una crema liscia. Sala.\n\n"
            "In una padella scalda l'olio con l'aglio, fallo dorare e toglilo. Versa la crema di peperoni e scalda a fiamma dolce, senza farla bollire.\n\n"
            "Lessa la pasta al dente e scolala tenendo un po' di acqua di cottura.\n\n"
            "Condiscila con la crema, il parmigiano e il basilico, allungando con l'acqua di cottura se serve. Servi con una macinata di pepe."
        ),
        "items": [
            {"name": "Pasta", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Peperoni", "quantity": 400, "unit": "g", "category": FRUTTA},
            {"name": "Panna", "quantity": 100, "unit": "ml", "category": LATTICINI},
            {"name": "Parmigiano", "quantity": 40, "unit": "g", "category": LATTICINI},
            {"name": "Basilico", "quantity": 10, "unit": "g", "category": FRUTTA},
            {"name": "Aglio", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Pasta e patate e provola", "servings": 4, "time_minutes": 45, "difficulty": "facile",
        "instructions": (
            "Soffriggi la cipolla tritata in olio a fiamma dolce finche' non e' trasparente.\n\n"
            "Aggiungi le patate a cubetti e falle insaporire 2 minuti, poi copri d'acqua (o di brodo) e sala. Cuoci 15 minuti, finche' le patate sono tenere ma non disfatte.\n\n"
            "Aggiungi la pasta e lessala direttamente nel brodo, mescolando ogni tanto: l'amido delle patate e della pasta addensa il liquido. Se serve aggiungi acqua calda.\n\n"
            "Quando la pasta e' al dente e il fondo e' cremoso, spegni.\n\n"
            "Manteca fuori dal fuoco con la provola a cubetti e il parmigiano, mescolando finche' il formaggio e' filante. Servi subito: questa pasta non si riscalda bene."
        ),
        "items": [
            {"name": "Pasta corta", "quantity": 320, "unit": "g", "category": CEREALI},
            {"name": "Patate", "quantity": 500, "unit": "g", "category": FRUTTA},
            {"name": "Provola", "quantity": 200, "unit": "g", "category": LATTICINI},
            {"name": "Parmigiano", "quantity": 50, "unit": "g", "category": LATTICINI},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Sale", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },

    # Scelte fra i piatti piu' cercati e amati degli ultimi anni: la classifica
    # dei primi piu' popolari per hashtag e ricerche (BonusFinder/Pasta Day 2024)
    # e le ricerche su Google del 2024-2025 (CiboToday, La Cucina Italiana).
    {
        "name": "Pasta alla Norma", "servings": 2, "time_minutes": 40, "difficulty": "media",
        "instructions": (
            "Taglia le melanzane a cubetti, cospargile di sale e lasciale 20 minuti in uno scolapasta, poi asciugale.\n\n"
            "Friggile in olio abbondante e ben caldo, poche alla volta, finche' non sono dorate. Scolale su carta assorbente e salale. In alternativa, cuocile al forno a 200°C con un filo d'olio, piu' leggere ma meno tradizionali.\n\n"
            "In una padella prepara la salsa: scalda l'olio con l'aglio, aggiungi la passata e cuoci 15 minuti. Togli l'aglio e aggiungi il basilico.\n\n"
            "Lessa la pasta al dente e scolala.\n\n"
            "Condiscila con la salsa, le melanzane fritte e abbondante ricotta salata grattugiata. Completa con basilico fresco e servi: la ricotta salata si scioglie col calore, quindi va aggiunta all'ultimo."
        ),
        "items": [
            {"name": "Penne", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Melanzane", "quantity": 400, "unit": "g", "category": FRUTTA},
            {"name": "Passata di pomodoro", "quantity": 400, "unit": "g", "category": DISPENSA},
            {"name": "Ricotta salata", "quantity": 60, "unit": "g", "category": LATTICINI},
            {"name": "Aglio", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Basilico", "quantity": 10, "unit": "g", "category": FRUTTA},
            {"name": "Olio", "quantity": 4, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Spaghetti all'assassina", "servings": 2, "time_minutes": 35, "difficulty": "media",
        "instructions": (
            "Questa pasta non si lessa: si cuoce direttamente in padella, come un risotto. Usa una padella larga e bassa, antiaderente.\n\n"
            "Scalda l'olio con il peperoncino (e uno spicchio d'aglio, se piace) a fiamma media. Disponi gli spaghetti crudi interi e falli tostare 2 minuti girandoli con una pinza: devono diventare lucidi e leggermente dorati.\n\n"
            "Aggiungi la passata e un mestolo di brodo caldo. Lascia che sobbolle senza mescolare troppo: la pasta deve attaccarsi leggermente al fondo e caramellizzare, ed e' proprio quella crosticina il segno distintivo del piatto.\n\n"
            "Quando il liquido si e' quasi asciugato, aggiungi un altro mestolo di brodo, mescolando e raschiando il fondo. Ripeti per 15-18 minuti, finche' gli spaghetti sono cotti e bruciacchiati ai bordi.\n\n"
            "Sono pronti quando sono asciutti, rossi e con qualche punto scuro. Servi subito: non e' una pasta da tenere."
        ),
        "items": [
            {"name": "Spaghetti", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Passata di pomodoro", "quantity": 400, "unit": "g", "category": DISPENSA},
            {"name": "Brodo", "quantity": 500, "unit": "ml", "category": DISPENSA},
            {"name": "Aglio", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Peperoncino", "quantity": 1, "unit": "pz", "category": DISPENSA},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Trofie al pesto", "servings": 2, "time_minutes": 25, "difficulty": "facile",
        "instructions": (
            "Per il pesto, se lo fai in casa: metti nel frullatore il basilico lavato e asciugato, i pinoli, l'aglio e il parmigiano. Frulla a scatti, aggiungendo l'olio a filo, finche' non ottieni una crema. Sala. Non frullare troppo a lungo: il basilico si ossida e annerisce.\n\n"
            "Se usi il pesto pronto, tienilo a temperatura ambiente: quello di frigo sa di meno.\n\n"
            "Porta a bollore l'acqua e lessa le trofie al dente.\n\n"
            "Scolale tenendo da parte un mestolo di acqua di cottura. Versa le trofie in una ciotola col pesto e allunga con l'acqua di cottura, mescolando: serve a farlo aderire alla pasta e ad ammorbidirlo.\n\n"
            "Servi subito con una foglia di basilico e, se piace, una grattugiata di parmigiano. Il pesto non va mai scaldato in padella: perderebbe profumo."
        ),
        "items": [
            {"name": "Trofie", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Basilico", "quantity": 40, "unit": "g", "category": FRUTTA},
            {"name": "Pinoli", "quantity": 30, "unit": "g", "category": DISPENSA},
            {"name": "Parmigiano", "quantity": 60, "unit": "g", "category": LATTICINI},
            {"name": "Aglio", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 6, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Sale", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },
    {
        "name": "Cacio e pepe", "servings": 2, "time_minutes": 20, "difficulty": "media",
        "instructions": (
            "Tosta il pepe nero in grani in una padella asciutta per 1 minuto, finche' non e' profumato, poi macinalo grossolanamente. Il pepe tostato e' meta' del piatto.\n\n"
            "Grattugia finemente il pecorino romano e mettilo in una ciotola.\n\n"
            "Lessa gli spaghetti in poca acqua (serve concentrata di amido), tenendoli bene al dente e togliendoli 2 minuti prima del tempo indicato.\n\n"
            "Versa un mestolo di acqua di cottura sul pecorino e mescola: si forma una crema densa senza grumi. Se e' troppo asciutta, aggiungi altra acqua poco per volta.\n\n"
            "Scalda la padella con il pepe tostato, versa la pasta e un po' di acqua di cottura. Manteca fuori dal fuoco, aggiungendo la crema di pecorino e mescolando energicamente: il calore residuo, non la fiamma, scioglie il formaggio. Se la padella e' troppo calda il pecorino si fila e si separa. Servi con altro pepe e pecorino."
        ),
        "items": [
            {"name": "Spaghetti", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Pecorino romano", "quantity": 80, "unit": "g", "category": LATTICINI},
            {"name": "Pepe nero", "quantity": 2, "unit": "cucchiaino", "category": DISPENSA},
            {"name": "Sale", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },
    {
        "name": "Bucatini all'amatriciana", "servings": 2, "time_minutes": 30, "difficulty": "media",
        "instructions": (
            "Taglia il guanciale a strisciette spesse mezzo centimetro. Mettilo in una padella fredda, senza olio, e accendi la fiamma dolce: il grasso deve sciogliersi lentamente e il guanciale dorarsi senza bruciare.\n\n"
            "Sfuma con il vino bianco e lascia evaporare, poi unisci la passata di pomodoro e un peperoncino. Cuoci 15-20 minuti a fiamma media, finche' il sugo non si e' ristretto e il grasso non affiora.\n\n"
            "Lessa i bucatini al dente in acqua poco salata: il guanciale e il pecorino sono gia' sapidi.\n\n"
            "Scolali tenendo un po' di acqua di cottura e versali nella padella col sugo. Salta 1 minuto.\n\n"
            "Spegni e completa con pecorino romano grattugiato, mescolando fuori dal fuoco: se aggiungi il formaggio a fiamma viva si rapprende. Servi subito."
        ),
        "items": [
            {"name": "Bucatini", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Guanciale", "quantity": 100, "unit": "g", "category": CARNE},
            {"name": "Pomodoro", "quantity": 400, "unit": "g", "category": FRUTTA},
            {"name": "Pecorino romano", "quantity": 50, "unit": "g", "category": LATTICINI},
            {"name": "Vino bianco", "quantity": 50, "unit": "ml", "category": BEVANDE},
            {"name": "Peperoncino", "quantity": 1, "unit": "pz", "category": DISPENSA},
            {"name": "Olio", "quantity": 1, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Penne all'arrabbiata", "servings": 2, "time_minutes": 25, "difficulty": "facile",
        "instructions": (
            "In una padella larga scalda l'olio con l'aglio schiacciato e il peperoncino spezzato. Falli insaporire 2 minuti a fiamma dolce, senza bruciarli.\n\n"
            "Togli l'aglio, aggiungi la passata di pomodoro e sala. Cuoci 15 minuti a fiamma media, finche' il sugo non si e' ristretto e il colore e' rosso vivo.\n\n"
            "Lessa le penne in acqua salata, tenendole al dente.\n\n"
            "Scolale e versale nella padella col sugo. Salta 1 minuto per farle insaporire, allungando con un po' di acqua di cottura se il sugo e' denso.\n\n"
            "Completa con prezzemolo tritato fresco e servi. Il prezzemolo va messo a fuoco spento: cotto perde profumo."
        ),
        "items": [
            {"name": "Penne", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Passata di pomodoro", "quantity": 400, "unit": "g", "category": DISPENSA},
            {"name": "Aglio", "quantity": 2, "unit": "pz", "category": FRUTTA},
            {"name": "Peperoncino", "quantity": 2, "unit": "pz", "category": DISPENSA},
            {"name": "Prezzemolo", "quantity": 10, "unit": "g", "category": FRUTTA},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Pasta fredda alla mediterranea", "servings": 4, "time_minutes": 25, "difficulty": "facile",
        "instructions": (
            "Porta a bollore l'acqua, salala e lessa la pasta al dente.\n\n"
            "Scolala e raffreddala subito sotto l'acqua corrente, oppure stendila su un vassoio con un filo d'olio: serve a fermare la cottura e a non farla appiccicare.\n\n"
            "Taglia i pomodorini a meta', la mozzarella a cubetti, il cetriolo a rondelle sottili e snocciola le olive.\n\n"
            "In una ciotola grande unisci la pasta fredda e le verdure. Condisci con olio, sale e il basilico spezzato a mano.\n\n"
            "Mescola bene e lascia riposare in frigorifero almeno 30 minuti: la pasta fredda ha bisogno di tempo per assorbire i sapori. Tira fuori 10 minuti prima di servire e aggiungi un filo d'olio crudo."
        ),
        "items": [
            {"name": "Pasta corta", "quantity": 320, "unit": "g", "category": CEREALI},
            {"name": "Pomodorini", "quantity": 300, "unit": "g", "category": FRUTTA},
            {"name": "Mozzarella", "quantity": 200, "unit": "g", "category": LATTICINI},
            {"name": "Olive", "quantity": 100, "unit": "g", "category": DISPENSA},
            {"name": "Cetriolo", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Basilico", "quantity": 10, "unit": "g", "category": FRUTTA},
            {"name": "Olio", "quantity": 4, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Casoncelli alla bergamasca", "servings": 4, "time_minutes": 50, "difficulty": "difficile",
        "instructions": (
            "Porta a bollore una pentola d'acqua abbondante e salala.\n\n"
            "In una padella larga sciogli il burro a fiamma dolce con le foglie di salvia. Aggiungi la pancetta tagliata a strisciette e falla dorare: il burro deve prendere il profumo della salvia senza bruciare.\n\n"
            "Butta i casoncelli e scolali appena risalgono a galla, con un mestolo forato: cuociono in 3-4 minuti e vanno maneggiati con delicatezza per non romperli.\n\n"
            "Versali nella padella col burro e la pancetta e saltali 1 minuto a fiamma viva, facendo attenzione a non romperli.\n\n"
            "Completa con grana grattugiato e, se piace, una macinata di pepe. Servi subito: i casoncelli freddi perdono tutto."
        ),
        "items": [
            {"name": "Casoncelli", "quantity": 400, "unit": "g", "category": CEREALI},
            {"name": "Burro", "quantity": 80, "unit": "g", "category": LATTICINI},
            {"name": "Pancetta", "quantity": 80, "unit": "g", "category": CARNE},
            {"name": "Grana", "quantity": 60, "unit": "g", "category": LATTICINI},
            {"name": "Salvia", "quantity": 10, "unit": "g", "category": FRUTTA},
        ],
    },
    {
        "name": "Malloreddus alla campidanese", "servings": 4, "time_minutes": 45, "difficulty": "media",
        "instructions": (
            "Sbriciola la salsiccia con le mani. Mettila in una padella con la cipolla tritata finissima e rosolala a fiamma media: la salsiccia deve perdere il rosa e la cipolla diventare dolce.\n\n"
            "Aggiungi la passata di pomodoro e lo zafferano sciolto in un cucchiaio d'acqua. Sala poco: la salsiccia e il pecorino sono gia' sapidi.\n\n"
            "Cuoci a fuoco basso 25 minuti, finche' il ragu' non si e' ristretto e non sa piu' di pomodoro crudo.\n\n"
            "Lessa i malloreddus in acqua salata, tenendoli al dente: sono gnocchetti di semola e tengono bene la cottura.\n\n"
            "Scolali e condiscili con il ragu', una spolverata di pecorino e, se piace, una foglia di basilico. Servi caldo."
        ),
        "items": [
            {"name": "Malloreddus", "quantity": 320, "unit": "g", "category": CEREALI},
            {"name": "Salsiccia", "quantity": 250, "unit": "g", "category": CARNE},
            {"name": "Passata di pomodoro", "quantity": 500, "unit": "g", "category": DISPENSA},
            {"name": "Zafferano", "quantity": 1, "unit": "pz", "category": DISPENSA},
            {"name": "Pecorino romano", "quantity": 50, "unit": "g", "category": LATTICINI},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Tagliolini al tartufo", "servings": 2, "time_minutes": 20, "difficulty": "facile",
        "instructions": (
            "Porta a bollore l'acqua per la pasta e salala con moderazione.\n\n"
            "In una padella larga sciogli il burro a fiamma dolce. Appena e' sciolto, aggiungi un mestolo di acqua di cottura e mescola: si forma una salsina emulsionata che avvolge la pasta senza ungerla troppo.\n\n"
            "Lessa i tagliolini: sono sottili e cuociono in 2-3 minuti, quindi stai attento a non scolarli tardi.\n\n"
            "Trasferiscili nella padella col burro e saltali delicatamente 30 secondi.\n\n"
            "Spegni la fiamma e aggiungi il tartufo affettato finissimo e il parmigiano. Il tartufo va messo a fuoco spento: il calore diretto distrugge il suo profumo, che e' tutto il piatto. Servi immediatamente."
        ),
        "items": [
            {"name": "Tagliolini", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Tartufo", "quantity": 20, "unit": "g", "category": DISPENSA},
            {"name": "Burro", "quantity": 50, "unit": "g", "category": LATTICINI},
            {"name": "Parmigiano", "quantity": 40, "unit": "g", "category": LATTICINI},
            {"name": "Sale", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },
    {
        "name": "Marry me chicken", "servings": 2, "time_minutes": 30, "difficulty": "facile",
        "instructions": (
            "Salale e infarina leggermente i petti di pollo, scuotendo via l'eccesso.\n\n"
            "Scalda l'olio in una padella larga e rosola il pollo 4 minuti per lato, finche' e' dorato. Tienilo da parte: finira' di cuocere nella salsa.\n\n"
            "Nella stessa padella, a fiamma dolce, scalda la panna con l'aglio tritato, i pomodori secchi a pezzetti e il parmigiano. Mescola finche' la salsa non e' liscia e il parmigiano sciolto.\n\n"
            "Rimetti il pollo nella padella, copri e cuoci 10 minuti a fiamma dolce, girandolo a meta' cottura.\n\n"
            "La salsa e' pronta quando si e' addensata e vela il dorso di un cucchiaio. Se e' troppo liquida, alza la fiamma un minuto senza coperchio. Completa con basilico fresco e servi con il fondo di cottura."
        ),
        "items": [
            {"name": "Pollo", "quantity": 400, "unit": "g", "category": CARNE},
            {"name": "Panna", "quantity": 200, "unit": "ml", "category": LATTICINI},
            {"name": "Parmigiano", "quantity": 50, "unit": "g", "category": LATTICINI},
            {"name": "Pomodori secchi", "quantity": 60, "unit": "g", "category": DISPENSA},
            {"name": "Aglio", "quantity": 2, "unit": "pz", "category": FRUTTA},
            {"name": "Basilico", "quantity": 10, "unit": "g", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Lasagna soup", "servings": 4, "time_minutes": 45, "difficulty": "facile",
        "instructions": (
            "In una pentola capiente rosola il macinato con la cipolla e l'aglio tritati, a fiamma media, finche' la carne non e' bruna e sgranata.\n\n"
            "Aggiungi la passata di pomodoro e il brodo. Sala, aggiungi un pizzico di origano e porta a bollore.\n\n"
            "Rompi le sfoglie di lasagne crude a pezzi di 3-4 centimetri e uniscile alla zuppa. Cuoci 12-15 minuti a fiamma media, mescolando ogni tanto: la pasta cuoce nel brodo e lo addensa con il suo amido.\n\n"
            "Assaggia e regola di sale. Se la zuppa si e' troppo ristretta, aggiungi brodo caldo.\n\n"
            "Servi in ciotole calde con un cucchiaio di ricotta e una spolverata di parmigiano: si sciolgono nel brodo bollente e completano il piatto. Qualche foglia di basilico fresco sopra."
        ),
        "items": [
            {"name": "Lasagne", "quantity": 250, "unit": "g", "category": CEREALI},
            {"name": "Macinato", "quantity": 400, "unit": "g", "category": CARNE},
            {"name": "Passata di pomodoro", "quantity": 700, "unit": "g", "category": DISPENSA},
            {"name": "Brodo", "quantity": 1, "unit": "l", "category": DISPENSA},
            {"name": "Ricotta", "quantity": 150, "unit": "g", "category": LATTICINI},
            {"name": "Parmigiano", "quantity": 50, "unit": "g", "category": LATTICINI},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Aglio", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Poke bowl", "servings": 2, "time_minutes": 30, "difficulty": "facile",
        "instructions": (
            "Cuoci il riso e lascialo intiepidire: una base calda scalda il pesce e non va bene per una poke bowl.\n\n"
            "Taglia il salmone a cubetti di circa 2 centimetri, eliminando la parte scura vicino alla pelle.\n\n"
            "Marinalo 10 minuti con salsa di soia, sesamo e succo di lime: poco tempo, per condire senza coprire il sapore del pesce.\n\n"
            "Taglia avocado e cetriolo a fette sottili e scotta gli edamame in acqua bollente 3 minuti, poi scolali.\n\n"
            "Componi la ciotola: uno strato di riso, poi salmone marinato, avocado, cetriolo ed edamame, divisi in settori per un piatto ordinato. Completa con semi di sesamo e, se piace, una punta di wasabi. Servi subito."
        ),
        "items": [
            {"name": "Riso", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Salmone", "quantity": 300, "unit": "g", "category": CARNE},
            {"name": "Avocado", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Cetriolo", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Edamame", "quantity": 100, "unit": "g", "category": FRUTTA},
            {"name": "Salsa di soia", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Sesamo", "quantity": 10, "unit": "g", "category": DISPENSA},
            {"name": "Lime", "quantity": 1, "unit": "pz", "category": FRUTTA},
        ],
    },
    {
        "name": "Riso alla cantonese", "servings": 2, "time_minutes": 25, "difficulty": "facile",
        "instructions": (
            "Il riso deve essere freddo: cuocilo in anticipo o usa gli avanzi del giorno prima. Il riso caldo, in padella, si stufa e diventa colloso.\n\n"
            "Sbatti le uova con un pizzico di sale e strapazzale in una padella con un filo d'olio, a fiamma media. Devono essere cotte ma morbide. Mettile da parte.\n\n"
            "Nella stessa padella, a fiamma alta, salta la cipolla tritata con i piselli e il prosciutto a cubetti per 3 minuti.\n\n"
            "Aggiungi il riso freddo e saltalo 2 minuti, sgranandolo con il cucchiaio: ogni chicco deve insaporirsi.\n\n"
            "Versa la salsa di soia lungo il bordo della padella (cosi' tosta e non bagna il riso) e mescola. Unisci le uova strapazzate e salta tutto insieme un minuto. Servi caldo."
        ),
        "items": [
            {"name": "Riso", "quantity": 180, "unit": "g", "category": CEREALI},
            {"name": "Uova", "quantity": 2, "unit": "pz", "category": LATTICINI},
            {"name": "Prosciutto", "quantity": 100, "unit": "g", "category": CARNE},
            {"name": "Piselli", "quantity": 100, "unit": "g", "category": SURGELATI},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Salsa di soia", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Gulasch", "servings": 4, "time_minutes": 90, "difficulty": "media",
        "instructions": (
            "Taglia la carne a cubetti di 3 centimetri. Asciugali con un canovaccio: una carne bagnata si lessa invece di rosolarsi.\n\n"
            "In una pentola pesante rosola la cipolla tritata in olio a fiamma dolce finche' non e' dorata, poi aggiungi la carne e falla rosolare a fiamma viva su tutti i lati.\n\n"
            "Togli dal fuoco un momento e unisci la paprica: a fiamma viva brucerebbe diventando amara. Mescola, poi rimetti sul fuoco.\n\n"
            "Sfuma con un po' di brodo, sala, copri e cuoci a fuoco basso un'ora. Il gulasch non si mescola troppo: la carne si sfa.\n\n"
            "Aggiungi le patate a cubetti e prosegui 30 minuti, finche' sono tenere e la carne si taglia con il cucchiaio. Se il sugo e' liquido, scopri e restringi a fiamma viva. Servi con pane."
        ),
        "items": [
            {"name": "Carne di manzo", "quantity": 600, "unit": "g", "category": CARNE},
            {"name": "Cipolla", "quantity": 2, "unit": "pz", "category": FRUTTA},
            {"name": "Patate", "quantity": 600, "unit": "g", "category": FRUTTA},
            {"name": "Paprica", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Passata di pomodoro", "quantity": 200, "unit": "g", "category": DISPENSA},
            {"name": "Brodo", "quantity": 700, "unit": "ml", "category": DISPENSA},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Pizza napoletana", "servings": 2, "time_minutes": 60, "difficulty": "difficile",
        "instructions": (
            "Sciogli il lievito in acqua tiepida (non calda, altrimenti muore). Impasta farina, acqua, lievito e sale fino a ottenere un impasto liscio ed elastico. Lavoralo 10 minuti sul piano infarinato.\n\n"
            "Copri e lascia lievitare 1-2 ore in un posto tiepido, finche' non raddoppia.\n\n"
            "Dividi l'impasto in panetti, stendili con le mani lasciando il bordo piu' alto: non usare il mattarello, schiaccia l'aria che serve a fare il cornicione.\n\n"
            "Preriscalda il forno alla massima temperatura con la teglia o la pietra dentro: una pizza in forno freddo non viene mai.\n\n"
            "Condisci con passata (poca), mozzarella asciutta a pezzetti e basilico. Inforna 6-8 minuti, finche' il bordo e' gonfio e macchiato di scuro. Servi subito, tagliata a spicchi."
        ),
        "items": [
            {"name": "Farina", "quantity": 400, "unit": "g", "category": CEREALI},
            {"name": "Lievito", "quantity": 1, "unit": "pz", "category": DISPENSA},
            {"name": "Passata di pomodoro", "quantity": 300, "unit": "g", "category": DISPENSA},
            {"name": "Mozzarella", "quantity": 200, "unit": "g", "category": LATTICINI},
            {"name": "Basilico", "quantity": 10, "unit": "g", "category": FRUTTA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Sale", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
        ],
    },
    {
        "name": "Paella", "servings": 4, "time_minutes": 60, "difficulty": "media",
        "instructions": (
            "Usa una padella larga e bassa, meglio se di ferro. Rosola il pollo a pezzi in olio a fiamma viva finche' non e' dorato, poi mettilo da parte.\n\n"
            "Nella stessa padella soffriggi i peperoni a strisciette e la cipolla. Aggiungi il pomodoro tritato e cuoci 5 minuti, finche' non si e' ridotto a una salsa scura.\n\n"
            "Unisci il riso e fallo insaporire 2 minuti nel soffritto, mescolando.\n\n"
            "Versa il brodo caldo con lo zafferano, sala e distribuisci il riso in modo uniforme. Da questo momento non mescolare piu': e' la regola della paella. Cuoci 18 minuti a fiamma media.\n\n"
            "A meta' cottura aggiungi i gamberi, le cozze e i piselli, affondandoli leggermente. Quando il brodo e' assorbito e il riso e' asciutto in superficie, alza la fiamma 1 minuto per formare la crosticina sul fondo (socarrat). Lascia riposare 5 minuti coperta e servi nella padella."
        ),
        "items": [
            {"name": "Riso", "quantity": 320, "unit": "g", "category": CEREALI},
            {"name": "Gamberi", "quantity": 200, "unit": "g", "category": CARNE},
            {"name": "Cozze", "quantity": 300, "unit": "g", "category": CARNE},
            {"name": "Pollo", "quantity": 300, "unit": "g", "category": CARNE},
            {"name": "Peperoni", "quantity": 200, "unit": "g", "category": FRUTTA},
            {"name": "Piselli", "quantity": 100, "unit": "g", "category": SURGELATI},
            {"name": "Zafferano", "quantity": 1, "unit": "pz", "category": DISPENSA},
            {"name": "Brodo", "quantity": 900, "unit": "ml", "category": DISPENSA},
            {"name": "Pomodoro", "quantity": 200, "unit": "g", "category": FRUTTA},
            {"name": "Olio", "quantity": 3, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Ramen", "servings": 2, "time_minutes": 45, "difficulty": "media",
        "instructions": (
            "Prepara il brodo: scalda il brodo in una pentola con miso, salsa di soia, zenzero grattugiato e cipolla. Porta a un leggero bollore e lascia sobbollire 15 minuti, per far fondere i sapori. Assaggia e regola di sale.\n\n"
            "Cuoci le uova: 6 minuti e mezzo in acqua bollente per un tuorlo morbido. Raffreddale subito in acqua ghiacciata e sgusciale con delicatezza. Tagliale a meta'.\n\n"
            "Cuoci i noodles in abbondante acqua, a parte, seguendo i tempi della confezione. Scolali senza sciacquarli.\n\n"
            "Rosola il maiale a fette in una padella calda finche' non e' dorato.\n\n"
            "Componi le ciotole: noodles sul fondo, poi versa il brodo bollente. Disponi sopra il maiale, le uova, l'alga nori e, se piace, i germogli e una punta di peperoncino. Servi bollente."
        ),
        "items": [
            {"name": "Noodles", "quantity": 200, "unit": "g", "category": CEREALI},
            {"name": "Brodo", "quantity": 1, "unit": "l", "category": DISPENSA},
            {"name": "Miso", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Carne di maiale", "quantity": 250, "unit": "g", "category": CARNE},
            {"name": "Uova", "quantity": 2, "unit": "pz", "category": LATTICINI},
            {"name": "Salsa di soia", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Zenzero", "quantity": 20, "unit": "g", "category": FRUTTA},
            {"name": "Alga nori", "quantity": 2, "unit": "pz", "category": DISPENSA},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
        ],
    },
    {
        "name": "Chicken tikka masala", "servings": 4, "time_minutes": 50, "difficulty": "media",
        "instructions": (
            "Taglia il pollo a bocconcini. Marina con lo yogurt, il curry, il garam masala e un pizzico di sale. Lascialo almeno 30 minuti, meglio un'ora in frigorifero: lo yogurt ammorbidisce la carne e la spezia la insaporisce fino in fondo.\n\n"
            "In una padella larga rosola cipolla, aglio e zenzero tritati in olio a fiamma dolce, finche' non sono dorati.\n\n"
            "Aggiungi la passata di pomodoro e cuoci 10 minuti, finche' il sugo non si e' ristretto.\n\n"
            "Unisci il pollo con tutta la marinata e rosolalo a fiamma viva 5 minuti, girandolo.\n\n"
            "Abbassa la fiamma, aggiungi la panna e cuoci 20 minuti, finche' il pollo e' tenero e la salsa cremosa. Se serve, allunga con un po' d'acqua. Completa con coriandolo fresco e servi con riso basmati."
        ),
        "items": [
            {"name": "Pollo", "quantity": 600, "unit": "g", "category": CARNE},
            {"name": "Yogurt", "quantity": 200, "unit": "g", "category": LATTICINI},
            {"name": "Panna", "quantity": 200, "unit": "ml", "category": LATTICINI},
            {"name": "Passata di pomodoro", "quantity": 400, "unit": "g", "category": DISPENSA},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Aglio", "quantity": 2, "unit": "pz", "category": FRUTTA},
            {"name": "Zenzero", "quantity": 20, "unit": "g", "category": FRUTTA},
            {"name": "Curry", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Garam masala", "quantity": 1, "unit": "cucchiaio", "category": DISPENSA},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
    {
        "name": "Shakshuka", "servings": 2, "time_minutes": 30, "difficulty": "facile",
        "instructions": (
            "Scalda l'olio in una padella larga con i bordi alti. Soffriggi la cipolla a fette sottili 5 minuti, finche' non e' morbida e dorata.\n\n"
            "Aggiungi i peperoni a strisciette e l'aglio tritato, poi le spezie: cumino, paprica e, se piace, un pizzico di peperoncino. Falli tostare 1 minuto nell'olio: e' il momento in cui sprigionano il profumo.\n\n"
            "Versa la passata di pomodoro, sala e cuoci 10 minuti a fiamma media, finche' il sugo non si e' ristretto e il liquido in eccesso e' evaporato.\n\n"
            "Con il dorso di un cucchiaio crea delle piccole conche nel sugo e apri un uovo in ciascuna, con delicatezza per non rompere il tuorlo.\n\n"
            "Copri la padella e cuoci 5-7 minuti a fiamma dolce: l'albume deve essere rappreso, il tuorlo ancora liquido. Servi direttamente in padella con pane abbrustolito da intingere."
        ),
        "items": [
            {"name": "Uova", "quantity": 4, "unit": "pz", "category": LATTICINI},
            {"name": "Passata di pomodoro", "quantity": 500, "unit": "g", "category": DISPENSA},
            {"name": "Peperoni", "quantity": 200, "unit": "g", "category": FRUTTA},
            {"name": "Cipolla", "quantity": 1, "unit": "pz", "category": FRUTTA},
            {"name": "Aglio", "quantity": 2, "unit": "pz", "category": FRUTTA},
            {"name": "Cumino", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
            {"name": "Paprica", "quantity": 1, "unit": "cucchiaino", "category": DISPENSA},
            {"name": "Pane", "quantity": 4, "unit": "fetta", "category": CEREALI},
            {"name": "Olio", "quantity": 2, "unit": "cucchiaio", "category": DISPENSA},
        ],
    },
]


# Preparazioni come erano prima di essere riscritte in modo piu' dettagliato
# (piu' passi, tempi e temperature). Servono a `semina()` per aggiornare le
# ricette gia' presenti nei database esistenti senza cancellare cio' che
# l'utente ha riscritto a mano: il testo si sostituisce solo se e' ancora
# esattamente quello vecchio. Non sono la fonte del ricettario: quella e'
# `RECIPES`.
PREPARAZIONI_PRECEDENTI = {
    'Pasta al pomodoro': "Soffriggi l'aglio nell'olio, aggiungi il pomodoro e cuoci 15 minuti. Lessa la pasta, condiscila con la salsa e aggiungi il basilico.",
    'Spaghetti alla carbonara': "Rosola il guanciale. Sbatti uova e pecorino con il pepe. Scola la pasta, mantecala fuori dal fuoco con guanciale e crema d'uovo.",
    'Risotto alla milanese': 'Tosta il riso, sfuma col vino, aggiungi il brodo poco alla volta. A metà cottura unisci lo zafferano, poi manteca con burro e parmigiano.',
    'Lasagne alla bolognese': 'Prepara il ragù con sedano, carota, cipolla e macinato. Alterna sfoglie, ragù, besciamella e parmigiano. Inforna a 180°C per 40 minuti.',
    'Parmigiana di melanzane': 'Griglia le melanzane. Alterna melanzane, passata, mozzarella e parmigiano. Inforna a 180°C per 35 minuti.',
    'Minestrone di verdure': "Soffriggi la cipolla, aggiungi le verdure a pezzi e la passata. Copri d'acqua e cuoci 30 minuti, poi aggiungi la pasta.",
    'Pollo al limone': 'Infarina il pollo e rosolalo nel burro. Sfuma con il succo di limone e completa la cottura, poi cospargi di prezzemolo.',
    'Insalata di riso': 'Lessa il riso e raffreddalo. Unisci tonno, mais, pomodorini, olive e mozzarella a pezzi, condisci con olio.',
    'Frittata di zucchine': 'Salta le zucchine con la cipolla. Sbatti le uova col parmigiano, unisci le zucchine e cuoci la frittata in padella.',
    'Cotoletta alla milanese': "Passa le fette nell'uovo e nel pangrattato. Cuocile nel burro finché sono dorate, servi con limone.",
    'Orata al forno': "Disponi le patate a fette in teglia, adagia l'orata e condisci con olio, limone e prezzemolo. Inforna a 200°C per 25 minuti.",
    'Nigiri di salmone': "Lava il riso finché l'acqua è limpida e lessalo, poi condiscilo con aceto di riso, zucchero e sale. Taglia il salmone a fette sottili, forma le palline di riso e appoggia il pesce sopra ogni boccone.",
    'Gnocchi al ragù': 'Prepara il ragù soffriggendo cipolla, carota e sedano con il macinato, poi aggiungi la passata e cuoci 40 minuti. Lessa gli gnocchi e condiscili con il ragù e il parmigiano.',
    'Croque madame': 'Prepara una besciamella e unisci la noce moscata. Componi i sandwich con pane, prosciutto e formaggio, coprili di besciamella e inforna a 200°C per 15 minuti. Adagia sopra un uovo al tegamino e servi.',
    'Pad thai': 'Ammolla i noodles in acqua calda. Salta aglio e gamberi nel wok, aggiungi i noodles, la salsa di soia, il lime e le uova sbattute. Completa con germogli di soia, arachidi e peperoncino.',
    'Spaghetti alle vongole': 'Fai aprire le vongole coperte in padella con aglio, olio e vino bianco. Lessa gli spaghetti, ripassali nel condimento con il prezzemolo.',
    'Fish & chips al forno': "Taglia le patate a bastoncini e condiscile con olio, poi inforna a 220°C. Passa i filetti di merluzzo nella farina, nell'uovo e nel pangrattato, e cuocili in forno finché sono dorati.",
    'Seppia impanata al forno': "Pulisci le seppie e tagliale ad anelli o a falde. Passale nell'uovo e nel pangrattato con il prezzemolo, poi cuocile su teglia oliata in forno a 200°C per 20 minuti, girandole a metà cottura.",
    'Calamarata': "Soffriggi aglio e peperoncino nell'olio, sfuma con il vino bianco e unisci i calamari a rondelle. Aggiungi la passata e cuoci 20 minuti. Lessa la calamarata, condiscila con il sugo e completa col prezzemolo.",
    'Gnocchi alla sorrentina': 'Prepara un sugo con aglio, olio e passata, e cuocilo 15 minuti. Lessa gli gnocchi, condiscili con il sugo e il basilico, trasferiscili in teglia con la mozzarella a cubetti e il parmigiano, e gratina in forno.',
    'Spaghetti aglio olio e peperoncino': "Scalda l'olio con l'aglio in camicia e il peperoncino a fiamma bassa, senza bruciarli. Lessa gli spaghetti e ripassali in padella con un po' d'acqua di cottura e il prezzemolo.",
    'Frittata di spaghetti': "Lessa gli spaghetti e condiscili con le uova sbattute, il parmigiano e il pepe. Versa tutto in padella con l'olio caldo, schiaccia bene e cuoci a fiamma dolce, girando la frittata a metà cottura.",
    'Tagliatelle al ragù bianco': 'Soffriggi cipolla, carota e sedano con il rosmarino, aggiungi il macinato e lascialo dorare. Sfuma col vino bianco, unisci il brodo e cuoci 40 minuti. Condisci le tagliatelle con il ragù e il parmigiano.',
    'Pasta con crema di peperoni': "Arrostisci i peperoni, pelali e frullali con la panna e un filo d'olio. Soffriggi l'aglio, versa la crema di peperoni e scalda. Lessa la pasta e condiscila con la crema, il parmigiano e il basilico.",
    'Pasta e patate e provola': "Soffriggi la cipolla nell'olio, aggiungi le patate a cubetti e copri d'acqua. Quando le patate sono tenere, lessa la pasta nel brodo, mantecala con la provola e il parmigiano fuori dal fuoco.",
    'Pasta alla Norma': "Friggi le melanzane a cubetti nell'olio e mettile da parte. Prepara la salsa con pomodoro e aglio, lessa la pasta e condiscila con la salsa, le melanzane, la ricotta salata e il basilico.",
    "Spaghetti all'assassina": "Tosta gli spaghetti crudi in padella con l'olio e il peperoncino. Aggiungi la passata e un mestolo di brodo per volta, lasciando che si asciughi fra un'aggiunta e l'altra, finche' la pasta e' bruciacchiata.",
    'Trofie al pesto': "Frulla basilico, pinoli, aglio e parmigiano con l'olio a filo. Lessa le trofie, condiscile con il pesto e allunga con un po' di acqua di cottura per farlo aderire.",
    'Cacio e pepe': 'Tosta il pepe in padella. Lessa gli spaghetti tenendoli al dente, poi mantecali fuori dal fuoco con pecorino e acqua di cottura fino a ottenere una crema liscia.',
    "Bucatini all'amatriciana": 'Rosola il guanciale, sfuma con il vino e aggiungi il pomodoro. Lessa i bucatini, condiscili con la salsa e completa con pecorino romano e peperoncino.',
    "Penne all'arrabbiata": 'Scalda olio, aglio e peperoncino. Unisci la passata e cuoci 15 minuti. Lessa le penne, condiscile con la salsa e cospargi di prezzemolo.',
    'Pasta fredda alla mediterranea': "Lessa la pasta, scolala e raffreddala sotto l'acqua. Condiscila con pomodorini, mozzarella a cubetti, olive, cetriolo e basilico, poi lasciala riposare in frigorifero.",
    'Casoncelli alla bergamasca': 'Lessa i casoncelli. Sciogli il burro con la salvia e la pancetta, poi saltaci la pasta. Completa con grana grattugiato.',
    'Malloreddus alla campidanese': 'Sbriciola la salsiccia e rosolala con la cipolla. Aggiungi la passata e lo zafferano. Lessa i malloreddus e condiscili con il ragù e una spolverata di pecorino.',
    'Tagliolini al tartufo': 'Sciogli il burro con un mestolo di acqua di cottura. Lessa i tagliolini e saltali nel burro, poi completa con tartufo affettato e parmigiano.',
    'Marry me chicken': "Rosola i petti di pollo e mettili da parte. Nella stessa padella scalda panna, aglio, pomodori secchi e parmigiano, rimetti il pollo e cuoci finche' la salsa si addensa.",
    'Lasagna soup': 'Rosola il macinato con cipolla e aglio. Aggiungi passata e brodo, poi rompi le sfoglie di lasagne nella zuppa e cuoci. Servi con ricotta e parmigiano.',
    'Poke bowl': 'Cuoci il riso e lascialo intiepidire. Taglia il salmone a cubetti e marinatelo con salsa di soia, sesamo e lime. Componi la ciotola con riso, salmone, avocado, cetriolo ed edamame.',
    'Riso alla cantonese': 'Sbatti le uova e strapazzale in padella. Salta cipolla, piselli e prosciutto, aggiungi il riso lessato e la salsa di soia, poi unisci le uova e salta tutto insieme.',
    'Gulasch': "Rosola la carne con la cipolla, sfuma con un po' di brodo e aggiungi la paprica. Cuoci a fuoco lento per un'ora, poi unisci le patate e prosegui finche' sono tenere.",
    'Pizza napoletana': 'Impasta farina, acqua, lievito e sale e lascia lievitare. Stendi i panetti, condisci con passata, mozzarella e basilico e cuoci alla massima temperatura per 6-8 minuti.',
    'Paella': "Rosola il pollo, poi aggiungi peperoni, pomodoro e riso. Copri con il brodo e lo zafferano e non mescolare piu'. A meta' cottura aggiungi gamberi, cozze e piselli.",
    'Ramen': 'Scalda il brodo con miso, salsa di soia, zenzero e cipolla. Cuoci i noodles a parte e lessa le uova. Componi la ciotola con brodo, noodles, maiale, uova e alga nori.',
    'Chicken tikka masala': 'Marina il pollo nello yogurt con curry e garam masala. Rosola cipolla, aglio e zenzero, aggiungi passata e panna, poi unisci il pollo e cuoci 20 minuti.',
    'Shakshuka': "Scalda olio, cipolla, peperoni, aglio e spezie. Aggiungi la passata e cuoci 10 minuti, poi apri le uova nel sugo, copri e prosegui finche' l'albume e' rappreso. Servi con il pane.",
}

# Ricette non più in elenco: vengono rimosse dal database per evitare che
# restino selezionabili nel piano pasti.
REMOVED = ["Pasta e fagioli", "Gnocchi al pesto", "Tiramisù"]

# Foto delle ricette: file in static/recipes/ con autore, licenza e provenienza.
# Sono immagini da Wikimedia Commons; dove l'abbinamento e' approssimativo il
# credito lo dichiara esplicitamente.
PHOTOS = {
    'Pasta al pomodoro': ('1-pasta-al-pomodoro-2.jpg',
        '10Rosso — CC BY 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Pasta_al_pomodoro_2.jpg'),
    'Cotoletta alla milanese': ('10-cotoletta-alla-milanese.jpg',
        'pier — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Cotoletta_alla_milanese.jpg'),
    'Orata al forno': ('11-orata-al-forno-con-patate.jpg',
        'DinaBenedettoFerrandina — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Orata_al_Forno_con_Patate.jpg'),
    'Nigiri di salmone': ('12-salmon-sushi-in-singapore.jpg',
        'puffballruns — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Salmon_Sushi_in_Singapore.jpg'),
    'Gnocchi al ragù': ('13-beef-ragu-with-gnocchi-lower-house-federation-square.jpg',
        'Alpha — CC BY-SA 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Beef_Ragu_with_Gnocchi_-_Lower_House,_Federation_Square.jpg'),
    'Croque madame': ('14-croque-madame-at-cafe-kocsi.jpg',
        'Kykk wiki — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Croque-madame_at_cafe_kocsi.jpg'),
    'Pad thai': ('15-pad-thai-at-good-catch-thai-urban-bistro-new-orleans.jpg',
        'pelican — CC BY-SA 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Pad_Thai_at_Good_Catch_Thai_Urban_Bistro,_New_Orleans.jpg'),
    'Spaghetti alle vongole': ('16-spaghetti-alle-vongole.jpg',
        'Flickr user: [2], retouched by AM — CC BY 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Spaghetti_alle_vongole.jpg'),
    'Fish & chips al forno': ('17-fish-and-chips-bath-uk.jpg',
        'Gvjekoslav — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Fish_and_Chips_Bath,_UK.jpg'),
    'Seppia impanata al forno': ('18-fried-calamari-ring.jpg',
        'Banej — CC BY-SA 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Fried_calamari_ring.jpg (immagine indicativa: calamari impanati, non seppia)'),
    'Calamarata': ('19-calamarata-al-rag-di-cernia-7097131809.jpg',
        'Diego from Roma, Italy — CC BY 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Calamarata_al_rag%C3%B9_di_Cernia_(7097131809).jpg'),
    'Spaghetti alla carbonara': ('2-spaghetti-alla-carbonara-3.jpg',
        'Lasagnolo9 at Italian Wikipedia (= formerly Ramagliolo9 at Italian Wikipedia) — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Spaghetti_alla_Carbonara_3.jpg'),
    'Gnocchi alla sorrentina': ('20-gnocchi-alla-sorrentina.jpg',
        'Davide Zambelli — CC BY 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Gnocchi_alla_sorrentina.jpg'),
    'Spaghetti aglio olio e peperoncino': ('21-spaghetti-aglio-olio-e-peperoncino-by-matsuyuki-retouched.jpg',
        'matsuyuki — CC BY-SA 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Spaghetti_aglio_olio_e_peperoncino_by_matsuyuki_retouched.jpg'),
    'Tagliatelle al ragù bianco': ('23-tagliatelle-al-rag.jpg',
        'Catia Giaccherini — CC BY-SA 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Tagliatelle_al_rag%C3%B9.jpg (immagine indicativa: ragù rosso, non bianco)'),
    'Pasta con crema di peperoni': ('24-pici-with-fried-onion-on-peppers-cream-32625760205.jpg',
        'Luca Nebuloni — CC BY 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Pici_with_fried_onion_on_peppers_cream_(32625760205).jpg (immagine indicativa: crema di peperoni)'),
    'Pasta e patate e provola': ('25-pasta-patate-e-provola.jpg',
        'Mojmir Churavy — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Pasta_Patate_e_Provola.jpg'),
    'Frittata di spaghetti': ('22-frittata-di-spaghetti.jpg',
        'Albertomos — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Frittata-di-spaghetti.jpg'),
    'Risotto alla milanese': ('3-risotto-alla-milanese.jpg',
        'Tamorlan — CC BY-SA 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Risotto_alla_milanese.JPG'),
    'Lasagne alla bolognese': ('4-lasagna-bolognese.jpg',
        'Sambawamba — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Lasagna_bolognese.jpg'),
    'Parmigiana di melanzane': ('5-parmigiana-di-melanzane.jpg',
        'Schellenberg — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Parmigiana_di_melanzane.jpg'),
    'Minestrone di verdure': ('6-minestrone-soup.jpg',
        'Katrin Morenz from Aachen, Deutschland — CC BY-SA 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Minestrone_soup.jpg'),
    'Pollo al limone': ('7-chicken-piccata.jpg',
        'Parkerman & Christie from San Diego, USA — CC BY 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Chicken_piccata.jpg (immagine indicativa: piatto analogo)'),
    'Insalata di riso': ('8-insalata-di-riso.jpg',
        'The original uploader was Auryg at Italian Wikipedia. — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Insalata_di_riso.jpg'),
    'Frittata di zucchine': ('9-omelette-aux-courgettes-ao-t-2020.jpg',
        'Benoît Prieur — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Omelette_aux_courgettes_(ao%C3%BBt_2020).jpg (immagine indicativa: frittata di zucchine)'),
    'Pasta alla Norma': ('26-pasta-alla-norma.jpg',
        '8w9d — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Pasta_alla_Norma_-_Wiki_Loves_Sicilia.jpg'),
    "Spaghetti all'assassina": ('27-spaghetti-allassassina.jpg',
        'ScotInPuglia — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Spaghetti_all%E2%80%99assassina,_Bari.jpg'),
    'Trofie al pesto': ('28-trofie-al-pesto.jpg',
        'Pastalovers — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Trofie_al_pesto_.jpg'),
    'Cacio e pepe': ('29-cacio-e-pepe.jpg',
        'Popo le Chien — CC BY-SA 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Cacio_e_pepe.jpg'),
    "Bucatini all'amatriciana": ('30-bucatini-allamatriciana.jpg',
        'stu_spivack — CC BY-SA 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Bucatini_(amatriciana_rossa).jpg'),
    "Penne all'arrabbiata": ('31-penne-allarrabbiata.jpg',
        'Petar Milošević — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Penne_Arrabbiata.jpg'),
    'Pasta fredda alla mediterranea': ('32-pasta-fredda-alla-mediterranea.jpg',
        'Brynn — CC BY-SA 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Pasta_salad_closeup.JPG (immagine indicativa: insalata di pasta)'),
    'Casoncelli alla bergamasca': ('33-casoncelli-alla-bergamasca.jpg',
        'Florixc — Public domain — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Casoncelli_in_una_grande_padella.jpg'),
    'Malloreddus alla campidanese': ('34-malloreddus-alla-campidanese.jpg',
        'Ewan Munro from London, UK — CC BY-SA 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Sardo_Cucina,_Fitzrovia,_London_(5147126888).jpg'),
    'Tagliolini al tartufo': ('35-tagliolini-al-tartufo.jpg',
        'Popo le Chien — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Taglioni_side.png (immagine indicativa: tagliolini, senza tartufo)'),
    'Marry me chicken': ('36-marry-me-chicken.jpg',
        'Andy Li — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:%22Marry_Me%22_Chicken_-_PizzaExpress,_Stanford_Cottage,_Worthing_2026-06-16.jpg'),
    'Lasagna soup': ('37-lasagna-soup.jpg',
        'Alessio Sbarbaro User_talk:Yoggysot — CC BY-SA 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Perbureira_01.jpg (immagine indicativa: zuppa di lasagne (perbureira), non la lasagna soup americana)'),
    'Poke bowl': ('38-poke-bowl.jpg',
        'Andy Li — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Salmon_Poke_Bowl_(S)_with_Spicy_mayo_sauce_-_Kitokito.jpg'),
    'Riso alla cantonese': ('39-riso-alla-cantonese.jpg',
        'Arnaud 25 — CC0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Riz_cantonais.jpg'),
    'Gulasch': ('40-gulasch.jpg',
        'Nikkol — CC BY-SA 1.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:%D0%93%D1%83%D0%BB%D1%8F%D1%88_78.jpg'),
    'Pizza napoletana': ('41-pizza-napoletana.jpg',
        'Valerio Capello at English Wikipedia — CC BY-SA 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Eq_it-na_pizza-margherita_sep2005_sml.jpg'),
    'Paella': ('42-paella.jpg',
        'Jan Harenburg — CC BY-SA 4.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:01_Paella_Valenciana_original.jpg'),
    'Ramen': ('43-ramen.jpg',
        'Lombroso — CC BY-SA 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Shoyu_ramen,_at_Kasukabe_Station_(2014.05.05)_2.jpg'),
    'Chicken tikka masala': ('44-chicken-tikka-masala.jpg',
        'Michael Hays — CC BY 2.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Chicken_tikka_masala_(cropped).jpg'),
    'Shakshuka': ('45-shakshuka.jpg',
        'Calliopejen1 — CC BY-SA 3.0 — Wikimedia Commons — https://commons.wikimedia.org/wiki/File:Shakshuka_by_Calliopejen1.jpg'),
}


def semina(percorso, remove=REMOVED, recipes=None, photos=None,
           precedenti=None, stampa=False):
    """Scrive il ricettario in `percorso`. Ritorna (aggiunte, rimosse, totali).

    Parla direttamente col database invece di usare le API: una casa appena
    creata non ha nessuna sessione, quindi le API risponderebbero 401. Le foto
    restano condivise in `static/recipes/`: sono file, non dati di una casa.
    """
    recipes = RECIPES if recipes is None else recipes
    photos = PHOTOS if photos is None else photos
    precedenti = PREPARAZIONI_PRECEDENTI if precedenti is None else precedenti
    per_nome = {r["name"]: r for r in recipes}
    with closing(sqlite3.connect(percorso)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")

        rimosse = 0
        for nome in remove:
            cur = db.execute("DELETE FROM recipes WHERE name = ?", (nome,))
            if cur.rowcount:
                rimosse += 1
                if stampa:
                    print(f"  rimossa: {nome}")

        esistenti = {r["name"] for r in db.execute("SELECT name FROM recipes")}
        aggiunte = 0
        for recipe in recipes:
            if recipe["name"] in esistenti:
                if stampa:
                    print(f"  saltata (già presente): {recipe['name']}")
                continue
            foto = photos.get(recipe["name"])
            rid = _inserisci_ricetta(db, recipe, foto)
            aggiunte += 1
            if stampa:
                print(f"  aggiunta: {recipe['name']}")
            esistenti.add(recipe["name"])

        # collega le foto anche alle ricette gia' presenti, senza toccare il resto
        aggiornate = 0
        for r in db.execute("SELECT id, name, image, image_credit FROM recipes"):
            foto = photos.get(r["name"])
            if not foto or (r["image"] == foto[0] and r["image_credit"] == foto[1]):
                continue
            db.execute("UPDATE recipes SET image = ?, image_credit = ? WHERE id = ?",
                       (foto[0], foto[1], r["id"]))
            aggiornate += 1
        if aggiornate and stampa:
            print(f"  {aggiornate} foto collegate alle ricette esistenti.")

        # Porta le preparazioni dettagliate alle ricette gia' presenti, ma solo
        # se il testo e' ancora quello vecchio: una preparazione riscritta a mano
        # dall'utente e' un dato suo e non va sovrascritta.
        preparate = 0
        for r in db.execute("SELECT id, name, instructions FROM recipes"):
            nuova = per_nome.get(r["name"], {}).get("instructions")
            if not nuova or r["instructions"] == nuova:
                continue
            if r["instructions"] != precedenti.get(r["name"]):
                continue
            db.execute("UPDATE recipes SET instructions = ? WHERE id = ?",
                       (nuova, r["id"]))
            preparate += 1
        if preparate and stampa:
            print(f"  {preparate} preparazioni aggiornate alle ricette esistenti.")

        totali = db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
        db.commit()
    return aggiunte, rimosse, totali


def _inserisci_ricetta(db, recipe, foto=None):
    """Inserisce una ricetta con i suoi ingredienti. Usa le stesse regole
    dell'API: le unita' passano da `units.normalize`, gli ingredienti sono
    condivisi per nome."""
    image, credito = (foto or ("", ""))
    cur = db.execute(
        "INSERT INTO recipes (name, servings, time_minutes, difficulty, instructions,"
        " image, image_credit) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (recipe["name"], recipe.get("servings", 2), recipe.get("time_minutes"),
         recipe.get("difficulty", "facile"), recipe.get("instructions", ""),
         image, credito if image else ""),
    )
    rid = cur.lastrowid
    for voce in recipe.get("items", []):
        unita = units.normalize(voce.get("unit"))
        ingrediente = app_module.get_or_create_ingredient(
            db, voce.get("name"), unita, voce.get("category", "Altro"))
        if ingrediente is None:
            continue
        db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit)"
                   " VALUES (?, ?, ?, ?)",
                   (rid, ingrediente, float(voce.get("quantity", 0) or 0), unita))
    return rid


def main():
    app_module.init_db()
    aggiunte, rimosse, totali = semina(
        os.environ["CUCINA_DB"], stampa=True)
    print(f"\n{aggiunte} aggiunte, {rimosse} rimosse, {totali} in totale.")
    print(f"Database: {os.environ['CUCINA_DB']}")


if __name__ == "__main__":
    main()
