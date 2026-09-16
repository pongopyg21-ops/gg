"""Popola il database con un ricettario italiano di partenza.

Idempotente: le ricette con un nome già presente vengono saltate.
Uso:  python3 seed.py            (usa CUCINA_DB, default cucina.db)
"""
import os
import sys

os.environ.setdefault("CUCINA_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "cucina.db"))

import app as app_module  # noqa: E402

FRUTTA = "Frutta e Verdura"
CARNE = "Carne e Pesce"
LATTICINI = "Latticini"
DISPENSA = "Dispensa"
CEREALI = "Pane e Cereali"
BEVANDE = "Bevande"
DOLCI = "Dolci"

RECIPES = [
    {
        "name": "Pasta al pomodoro", "servings": 2, "time_minutes": 20, "difficulty": "facile",
        "instructions": "Soffriggi l'aglio nell'olio, aggiungi il pomodoro e cuoci 15 minuti. "
                        "Lessa la pasta, condiscila con la salsa e aggiungi il basilico.",
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
        "instructions": "Rosola il guanciale. Sbatti uova e pecorino con il pepe. "
                        "Scola la pasta, mantecala fuori dal fuoco con guanciale e crema d'uovo.",
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
        "instructions": "Tosta il riso, sfuma col vino, aggiungi il brodo poco alla volta. "
                        "A metà cottura unisci lo zafferano, poi manteca con burro e parmigiano.",
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
        "instructions": "Prepara il ragù con sedano, carota, cipolla e macinato. "
                        "Alterna sfoglie, ragù, besciamella e parmigiano. Inforna a 180°C per 40 minuti.",
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
        "instructions": "Griglia le melanzane. Alterna melanzane, passata, mozzarella e parmigiano. "
                        "Inforna a 180°C per 35 minuti.",
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
        "instructions": "Soffriggi la cipolla, aggiungi le verdure a pezzi e la passata. "
                        "Copri d'acqua e cuoci 30 minuti, poi aggiungi la pasta.",
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
        "instructions": "Infarina il pollo e rosolalo nel burro. Sfuma con il succo di limone "
                        "e completa la cottura, poi cospargi di prezzemolo.",
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
        "instructions": "Lessa il riso e raffreddalo. Unisci tonno, mais, pomodorini, olive e "
                        "mozzarella a pezzi, condisci con olio.",
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
        "instructions": "Salta le zucchine con la cipolla. Sbatti le uova col parmigiano, "
                        "unisci le zucchine e cuoci la frittata in padella.",
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
        "instructions": "Passa le fette nell'uovo e nel pangrattato. Cuocile nel burro "
                        "finché sono dorate, servi con limone.",
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
        "instructions": "Disponi le patate a fette in teglia, adagia l'orata e condisci con "
                        "olio, limone e prezzemolo. Inforna a 200°C per 25 minuti.",
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
        "instructions": "Lava il riso finché l'acqua è limpida e lessalo, poi condiscilo con "
                        "aceto di riso, zucchero e sale. Taglia il salmone a fette sottili, "
                        "forma le palline di riso e appoggia il pesce sopra ogni boccone.",
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
        "instructions": "Prepara il ragù soffriggendo cipolla, carota e sedano con il macinato, "
                        "poi aggiungi la passata e cuoci 40 minuti. Lessa gli gnocchi e condiscili "
                        "con il ragù e il parmigiano.",
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
        "instructions": "Prepara una besciamella e unisci la noce moscata. Componi i sandwich "
                        "con pane, prosciutto e formaggio, coprili di besciamella e inforna a "
                        "200°C per 15 minuti. Adagia sopra un uovo al tegamino e servi.",
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
        "instructions": "Ammolla i noodles in acqua calda. Salta aglio e gamberi nel wok, "
                        "aggiungi i noodles, la salsa di soia, il lime e le uova sbattute. "
                        "Completa con germogli di soia, arachidi e peperoncino.",
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
        "instructions": "Fai aprire le vongole coperte in padella con aglio, olio e vino bianco. "
                        "Lessa gli spaghetti, ripassali nel condimento con il prezzemolo.",
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
        "instructions": "Taglia le patate a bastoncini e condiscile con olio, poi inforna a 220°C. "
                        "Passa i filetti di merluzzo nella farina, nell'uovo e nel pangrattato, "
                        "e cuocili in forno finché sono dorati.",
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
        "instructions": "Pulisci le seppie e tagliale ad anelli o a falde. Passale nell'uovo e "
                        "nel pangrattato con il prezzemolo, poi cuocile su teglia oliata in forno "
                        "a 200°C per 20 minuti, girandole a metà cottura.",
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
        "instructions": "Soffriggi aglio e peperoncino nell'olio, sfuma con il vino bianco e "
                        "unisci i calamari a rondelle. Aggiungi la passata e cuoci 20 minuti. "
                        "Lessa la calamarata, condiscila con il sugo e completa col prezzemolo.",
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
        "instructions": "Prepara un sugo con aglio, olio e passata, e cuocilo 15 minuti. "
                        "Lessa gli gnocchi, condiscili con il sugo e il basilico, trasferiscili "
                        "in teglia con la mozzarella a cubetti e il parmigiano, e gratina in forno.",
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
        "instructions": "Scalda l'olio con l'aglio in camicia e il peperoncino a fiamma bassa, "
                        "senza bruciarli. Lessa gli spaghetti e ripassali in padella con un po' "
                        "d'acqua di cottura e il prezzemolo.",
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
        "instructions": "Lessa gli spaghetti e condiscili con le uova sbattute, il parmigiano "
                        "e il pepe. Versa tutto in padella con l'olio caldo, schiaccia bene e "
                        "cuoci a fiamma dolce, girando la frittata a metà cottura.",
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
        "instructions": "Soffriggi cipolla, carota e sedano con il rosmarino, aggiungi il "
                        "macinato e lascialo dorare. Sfuma col vino bianco, unisci il brodo e "
                        "cuoci 40 minuti. Condisci le tagliatelle con il ragù e il parmigiano.",
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
        "instructions": "Arrostisci i peperoni, pelali e frullali con la panna e un filo d'olio. "
                        "Soffriggi l'aglio, versa la crema di peperoni e scalda. Lessa la pasta e "
                        "condiscila con la crema, il parmigiano e il basilico.",
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
        "instructions": "Soffriggi la cipolla nell'olio, aggiungi le patate a cubetti e copri "
                        "d'acqua. Quando le patate sono tenere, lessa la pasta nel brodo, "
                        "mantecala con la provola e il parmigiano fuori dal fuoco.",
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
]

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
}


def main():
    app_module.init_db()
    client = app_module.app.test_client()
    esistenti = {r["name"]: r["id"] for r in client.get("/api/recipes").get_json()}

    rimosse = 0
    for nome in REMOVED:
        rid = esistenti.get(nome)
        if rid is None:
            continue
        client.delete(f"/api/recipes/{rid}")
        rimosse += 1
        print(f"  rimossa: {nome}")

    aggiunte = 0
    for recipe in RECIPES:
        if recipe["name"] in esistenti:
            print(f"  saltata (già presente): {recipe['name']}")
            continue
        photo = PHOTOS.get(recipe["name"])
        if photo:
            recipe = dict(recipe, image=photo[0], image_credit=photo[1])
        response = client.post("/api/recipes", json=recipe)
        if response.status_code != 201:
            print(f"  ERRORE su {recipe['name']}: {response.get_json()}", file=sys.stderr)
            continue
        aggiunte += 1
        print(f"  aggiunta: {recipe['name']}")

    # collega le foto anche alle ricette gia' presenti, senza toccare il resto
    aggiornate = 0
    for recipe in client.get("/api/recipes").get_json():
        photo = PHOTOS.get(recipe["name"])
        if not photo:
            continue
        dettaglio = client.get(f"/api/recipes/{recipe['id']}").get_json()
        if dettaglio.get("image") == photo[0] and dettaglio.get("image_credit") == photo[1]:
            continue
        dettaglio["image"] = photo[0]
        dettaglio["image_credit"] = photo[1]
        client.put(f"/api/recipes/{recipe['id']}", json=dettaglio)
        aggiornate += 1
    if aggiornate:
        print(f"\n{aggiornate} foto collegate alle ricette esistenti.")

    totali = client.get("/api/recipes").get_json()
    print(f"\n{aggiunte} aggiunte, {rimosse} rimosse, {len(totali)} in totale.")
    print(f"Database: {os.environ['CUCINA_DB']}")


if __name__ == "__main__":
    main()
