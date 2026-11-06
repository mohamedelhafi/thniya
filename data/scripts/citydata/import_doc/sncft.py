"""Import du réseau SNCFT depuis la base de connaissances `doc/` (specs/04e-import-doc.md).

Sources lues (fichiers retravaillés, voir doc/trains-banlieue/ et doc/trains-grandes-lignes/) :

- `trains-banlieue/donnees/gares-banlieue.csv` et `trains-grandes-lignes/donnees/gares-grandes-lignes.csv` : gares
  ordonnées par ligne, noms FR/AR (affiches), coordonnées (data.transport.tn, OSM, GTFS SNCFT 2020-2021) ;
- `…/horaires-*-hiver-2026-2027.csv` : passages gare par gare (format long), coquilles corrigées (statut I) ;
- `trains-banlieue/donnees/tarifs-banlieue-gtfs-2020-2021.csv` : derniers tarifs connus (banlieue sud, Sahel) ;
- `sources-open-data/raw/osm/geofabrik_2026-10-13/railway_stations.geojson` : référence OSM précise des gares dont la
  position vient d'OSM, et recoupement des autres.

Écrit :

- `places/sncft/gares.yaml` : une gare = un lieu, même desservie par plusieurs lignes ; les gares déjà définies ailleurs
  (banlieue sud saisie à la main) sont réutilisées, jamais redéfinies ;
- `networks/sncft/lines/*.yaml` + grilles `timetables/<ligne>/HIVER-2026-2027/NORMAL/TOUS/<DIRECTION>.csv` (§9) ;
- `networks/sncft/fares/*.yaml` : derniers tarifs connus, en ESTIMATION (l'app affiche « environ »).

Ne touche jamais à la banlieue sud saisie à la main (ligne, grilles, gares) : elle est seulement comparée à doc/.
"""

import csv
import io
import json
import re
from collections import defaultdict
from pathlib import Path

from citydata.geo import contrast_ratio
from citydata.import_doc.common import (clean_ar, dist_m, doc_path, hhmm, i18n, in_tunisia, is_generated, minutes,
                                        norm_name, prov, read_csv, remove_generated, write_text, write_yaml,
                                        dt_to_millimes)
from citydata.loader import read_yaml

_od = dict   # dictionnaires ordonnés (ordre d'insertion), sérialisables par yaml.safe_dump
NETWORK = "SNCFT"
VERSION = "HIVER-2026-2027"
VALID_FROM, VALID_TO = "2026-09-01", "2027-06-30"
OUV, SAM, DIM = "OUVRABLE", "SAMEDI", "DIMANCHE"

GARES_BANLIEUE = ("trains-banlieue", "donnees", "gares-banlieue.csv")
GARES_GL = ("trains-grandes-lignes", "donnees", "gares-grandes-lignes.csv")
HORAIRES_BANLIEUE = ("trains-banlieue", "donnees", "horaires-banlieue-hiver-2026-2027.csv")
HORAIRES_GL = ("trains-grandes-lignes", "donnees", "horaires-grandes-lignes-hiver-2026-2027.csv")
TARIFS_BANLIEUE = ("trains-banlieue", "donnees", "tarifs-banlieue-gtfs-2020-2021.csv")
OSM_STATIONS = ("sources-open-data", "raw", "osm", "geofabrik_2026-10-13", "railway_stations.geojson")

PLACES_FILE = "places/sncft/gares.yaml"
NET_DIR = "networks/sncft"
HAND_LINE = "networks/sncft/lines/banlieue-sud.yaml"          # saisi à la main : comparé, jamais écrit
HAND_GRIDS = "networks/sncft/timetables/banlieue-sud/HIVER-2026-2027/NORMAL/TOUS"

UP = "https://www.sncft.com.tn/wp-content/uploads/2026/09/"
PAGE_BANLIEUE = "https://www.sncft.com.tn/voyageurs/banlieue-tunis/"
PAGE_SAHEL = "https://www.sncft.com.tn/voyageurs/banlieue-sahel/"
PAGE_GL = "https://www.sncft.com.tn/voyageurs/horaires/"

# Jeux data.transport.tn d'où viennent les coordonnées (colonne source_coord des CSV de gares)
DTT_SETS = {
    "grandes lignes": "« Position géographique des stations du réseau grandes lignes de la SNCFT »",
    "banlieue sud": "« Cartographie des stations de la banlieue sud SNCFT »",
    "banlieue sahel": "« Cartographie des stations de la banlieue du Sahel SNCFT »",
    "rfr": "« Cartographie des stations du réseau ferroviaire rapide (RFR) »",
}

# Noms d'affichage : la partie entre parenthèses des noms de doc/ devient un alias, sauf quand elle lève une ambiguïté.
DISPLAY_NAMES = {
    "LA-FACULTE-2": ("La Faculté 2", "الكلية 2"),
    "AEROPORT-MONASTIR": ("L'Aéroport (Monastir-Skanès)", "المطار (المنستير)"),
    "MAHDIA-EZZAHRA": ("Ezzahra (Mahdia)", "الزهراء (المهدية)"),
    "MANOUBA": ("Manouba", "منوبة"),
    "SOUSSE": ("Sousse", "سوسة"),
}
EXTRA_ALIASES = {
    "SAIDA-MANOUBIA": ["sayada mannoubia", "saida mannoubia"],
    "KSIBET-BENNANE": ["ksibet el mediouni", "bennane"],
    "SOUSSE": ["sousse voyageurs", "gare de sousse"],
    "LA-FACULTE-2": ["la faculté (2e arrêt)"],
    "MANOUBA": ["mannouba"],
}

# --- Codes « jours de circulation » -------------------------------------------------------------------------------

def _code(days, fr, ar):
    return {"days": days, "label": {"fr": fr, "ar": ar}}


TOUS = _code([OUV, SAM, DIM], "Tous les jours", "كامل أيام الأسبوع")
BANLIEUE_CODES = {   # affiches des banlieues de Tunis (mêmes libellés que banlieue-sud.yaml)
    "-": TOUS,
    "A": _code([OUV, SAM], "Sauf dimanches et fêtes", "ما عدى الآحاد و الأعياد"),
    "B": _code([DIM], "Dimanches et fêtes seulement", "أيام الآحاد و الأعياد"),
}
SAUF_DIM = _code([OUV, SAM], "Tous les jours sauf dimanches et fêtes", "كل الأيام ما عدا الآحاد و العطل الرسمية")
DIM_SEUL = _code([DIM], "Dimanches et fêtes seulement", "أيام الآحاد و العطل الرسمية")

# --- Lignes ---------------------------------------------------------------------------------------------------------
# src : (fichier d'horaires, valeur de la colonne « ligne ») ; directions : sens de doc/ → direction ; patterns : None =
# ligne simple (un parcours par direction, déduit des trains), sinon parcours explicites dans l'ordre de recherche
# (le premier qui contient les gares desservies d'un train est le sien, comme dans le générateur).

L5_TRONC = ["TUNIS-VILLE", "HAMMAM-LIF", "BORJ-CEDRIA", "GROMBALIA", "BOU-ARGOUB", "BIR-BOU-REGBA", "BOUFICHA",
            "ENFIDHA", "KALAA-KEBIRA", "KALAA-SEGHIRA"]
L5_SFAX = ["KERKER", "EL-JEM", "LA-HENCHA", "SAKIET-EZZIT", "SFAX", "MAHRES", "GHRAIBA"]
L5_GAFSA = ["MAKNASSY", "SENED", "GAFSA", "METLAOUI", "EL-OUEDIANE", "TOZEUR"]
L6_TRONC = ["TUNIS-VILLE", "JEBEL-JELLOUD", "BIR-KASSAA", "NAASSEN", "KHELIDIA", "OUDNA", "CHEYLUS", "BIR-MCHERGA",
            "DEPIENNE", "PONT-DU-FAHS", "BOU-ARADA", "EL-AROUSSA", "SIDI-AYED", "GAAFOUR", "EL-AKHOUAT", "EL-KRIB",
            "SIDI-BOU-ROUIS", "TRIKA", "LE-SERS"]
L6_KK = ["LES-SALINES", "LES-ZOUARINES", "DAHMANI", "AIN-MESRIA", "FEJ-ET-TAMEUR", "GOURAIA", "OUED-SARRATH",
         "KALAA-KHASBA"]


def _rev(stops):
    return list(reversed(stops))


LINES = [
    {
        "key": "RFR-E", "id": "SNCFT-E", "file": "rfr-e", "public_code": "E", "color": "#00796B",
        "name": ("Ligne E", "الخط E"), "long_name": ("Tunis – Bougatfa", "تونس – بوقطفة"),
        "src": ("banlieue", "RFR-E"), "gares": ("banlieue", "RFR-E"),
        "directions": [("BOUGATFA", "Tunis -> Bougatfa", "BOUGATFA", False),
                       ("TUNIS", "Bougatfa -> Tunis", "TUNIS-VILLE", True)],
        "codes": BANLIEUE_CODES, "fare": "FARE-SNCFT-E",
        "affiche": ("« Horaires des trains banlieue de Tunis » hiver 2026-2027, Tunis – Bougatfa, valable du "
                    "1er septembre 2026 au 30 juin 2027", UP + "Horaire-Bougatfa-Tunis-hiver-26-27-_1_-_1_-1-scaled.webp",
                    PAGE_BANLIEUE),
    },
    {
        "key": "RFR-D", "id": "SNCFT-D", "file": "rfr-d", "public_code": "D", "color": "#AD1457",
        "name": ("Ligne D", "الخط D"), "long_name": ("Tunis – Gobaa Ville", "تونس – القباعة المدينة"),
        "src": ("banlieue", "RFR-D"), "gares": ("banlieue", "RFR-D"),
        "directions": [("GOBAA", "Tunis -> Gobaa Ville", "GOBAA-VILLE", False),
                       ("TUNIS", "Gobaa Ville -> Tunis", "TUNIS-VILLE", True)],
        "codes": BANLIEUE_CODES, "fare": None,
        "missing_stop_notes": {"GOBAA-VILLE": (
            "gobaa", "Le train dessert aussi Gobaa Ville, terminus de la ligne (gare non représentée : position inconnue)",
            "يؤمن القطار أيضا محطة القباعة المدينة")},
        "affiche": ("« Horaires des trains banlieue de Tunis » hiver 2026-2027, Tunis – Gobaa Ville, valable du "
                    "1er septembre 2026 au 30 juin 2027", UP + "Horaire-Gobaa-Tunis-hiver-26-27-_1_-1-scaled.webp",
                    PAGE_BANLIEUE),
    },
    {
        "key": "SAHEL", "id": "SNCFT-SAHEL", "file": "metro-sahel", "public_code": "MS", "color": "#BF360C",
        "name": ("Métro du Sahel", "مترو الساحل"),
        "long_name": ("Sousse Bab Jedid – Monastir – Mahdia", "سوسة باب الجديد – المنستير – المهدية"),
        "src": ("banlieue", "SAHEL"), "gares": ("banlieue", "SAHEL"),
        "directions": [("MAHDIA", "Sousse Bab Jedid -> Mahdia", "MAHDIA", False),
                       ("SOUSSE", "Mahdia -> Sousse Bab Jedid", "SOUSSE-BAB-JEDID", True)],
        "codes": {"-": TOUS}, "fare": "FARE-SNCFT-SAHEL",
        "affiche": ("« Horaires des trains Mahdia – Monastir – Sousse » hiver 2026-2027 (titrée « 2027-2026 », dates de "
                    "validité et codes de jours non imprimés : dates de l'horaire d'hiver des banlieues SNCFT, "
                    "circulation supposée quotidienne)", UP + "conception-3_page-0001-_1_.webp", PAGE_SAHEL),
    },
    {
        "key": "L5", "id": "SNCFT-L5", "file": "ligne-5", "public_code": "5", "color": "#4527A0",
        "name": ("Tunis – Sfax – Gabès / Tozeur", "تونس – صفاقس – قابس / توزر"),
        "long_name": ("Tunis – Bir Bou Regba – Sousse – Monastir – Mahdia – Sfax – Gabès – Gafsa – Métlaoui – Tozeur",
                      "تونس – بئر بورقبة – سوسة – المنستير – المهدية – صفاقس – قابس – قفصة – المتلوي – توزر"),
        "src": ("gl", "L5 Tunis-Sousse-Sfax-Gabès/Tozeur"), "gares": ("gl", "L5 Tunis-Sousse-Sfax-Gabès/Tozeur"),
        "directions": [("SUD", "Tunis -> sud", "GABES", False), ("TUNIS", "sud -> Tunis", "TUNIS-VILLE", True)],
        "patterns": {
            "SUD": [("SUD-GABES-DIRECT", L5_TRONC + ["MESSAADINE"] + L5_SFAX + ["GABES"], False),
                    ("SUD-MAHDIA", L5_TRONC + ["MESSAADINE", "MONASTIR", "MAHDIA"], False),
                    ("SUD-GABES", L5_TRONC + ["SOUSSE", "MESSAADINE"] + L5_SFAX + ["GABES"], True),
                    ("SUD-TOZEUR", L5_TRONC + ["SOUSSE", "MESSAADINE"] + L5_SFAX + L5_GAFSA, False)],
            "TUNIS": [("NORD-GABES", _rev(L5_TRONC + ["SOUSSE", "MESSAADINE"] + L5_SFAX + ["GABES"]), True),
                      ("NORD-TOZEUR", _rev(L5_TRONC + ["SOUSSE", "MESSAADINE"] + L5_SFAX + L5_GAFSA), False),
                      ("NORD-MAHDIA", _rev(L5_TRONC + ["SOUSSE", "MESSAADINE", "MONASTIR", "MAHDIA"]), False)],
        },
        "codes": {"-": TOUS,
                  "A": _code([OUV, DIM], "Tous les jours sauf les samedis et les veilles de fêtes",
                             "كل الأيام ما عدا السبت و الأيام التي تسبق العطل الرسمية"),
                  # (A) de la page retour : même lettre, autre sens ; clé distincte dans la ligne
                  "A2": _code([OUV, SAM], "Tous les jours sauf les dimanches et fêtes",
                              "كل الأيام ما عدا الآحاد و العطل الرسمية")},
        "day_text": {"tous les jours sauf samedis et veilles de fêtes": "A",
                     "tous les jours sauf dimanches et fêtes": "A2"},
        "fare": None,
        "missing_stop_notes": {"EL-OUEDIANE": (
            "ouediane", "Dessert aussi El Ouediane (gare non représentée : position inconnue)",
            "يتوقف أيضا بمحطة الوديان")},
        "affiche": ("« Horaires des trains Grandes Lignes » ligne 5 Tunis – Tozeur, du 1er septembre 2026 au 30 juin "
                    "2027 sauf mois de Ramadan (pages 1 et 2)",
                    UP + "L-5-TUNIS-TOZEUR-Hiver-2026-2027-1_page-0001-1-scaled.jpg et …page-0002-1-scaled.jpg",
                    PAGE_GL),
    },
    {
        "key": "REDEYEF", "id": "SNCFT-REDEYEF", "file": "redeyef-metlaoui", "public_code": "RM", "color": "#37474F",
        "name": ("Redeyef – Métlaoui", "الرديف – المتلوي"),
        "long_name": ("Redeyef – Moularès – Métlaoui", "الرديف – أم العرايس – المتلوي"),
        "src": ("gl", "Redeyef-Moularès-Métlaoui"), "gares": ("gl", "Redeyef-Moularès-Métlaoui"),
        "directions": [("METLAOUI", "Redeyef -> Métlaoui", "METLAOUI", False),
                       ("REDEYEF", "Métlaoui -> Redeyef", "REDEYEF", True)],
        "codes": {"-": TOUS},
        "day_text": {"correspondance à Métlaoui avec le 13-5/72 vers Tunis": "-",
                     "correspondance à Métlaoui avec le 5-13/57 (Tunis -> Tozeur)": "-"},
        "text_notes": {
            "correspondance à Métlaoui avec le 13-5/72 vers Tunis": (
                "corr72", "Correspondance à Métlaoui avec le train 13-5/72 à destination de Tunis",
                "الربط في محطة المتلوي مع القطار 13-5/72 في اتجاه تونس"),
            "correspondance à Métlaoui avec le 5-13/57 (Tunis -> Tozeur)": (
                "corr57", "Correspondance à Métlaoui avec le train 5-13/57 (Tunis – Tozeur)",
                "الربط في محطة المتلوي مع القطار 5-13/57 في اتجاه توزر")},
        "fare": None,
        "affiche": ("« Horaires des trains Grandes Lignes » ligne 5, cartouche Redeyef – Moularès – Métlaoui, du "
                    "1er septembre 2026 au 30 juin 2027 sauf mois de Ramadan",
                    UP + "L-5-TUNIS-TOZEUR-Hiver-2026-2027-1_page-0001-1-scaled.jpg", PAGE_GL),
    },
    {
        "key": "TA", "id": "SNCFT-GHARDIMAOU", "file": "tunis-ghardimaou", "public_code": "TA", "color": "#283593",
        "name": ("Tunis – Ghardimaou", "تونس – غار الدماء"),
        "long_name": ("Tunis – Tebourba – Béja – Bou Salem – Jendouba – Ghardimaou",
                      "تونس – طبربة – باجة – بوسالم – جندوبة – غار الدماء"),
        "src": ("gl", "Tunis-Béja-Jendouba-Ghardimaou (-Annaba)"),
        "gares": ("gl", "Tunis-Béja-Jendouba-Ghardimaou (-Annaba)"),
        "directions": [("GHARDIMAOU", "Tunis -> Ghardimaou", "GHARDIMAOU", False),
                       ("TUNIS", "Ghardimaou -> Tunis", "TUNIS-VILLE", True)],
        "codes": {"-": TOUS}, "fare": None,
        "affiche": ("« Horaires des trains Grandes Lignes » Tunis – Ghardimaou – Annaba, du 1er septembre 2026 au "
                    "30 juin 2027 sauf mois de Ramadan", UP + "LTA-TUNIS-ANNABA-Hiver-2026.2027-1_page-0001-1-scaled.jpg",
                    PAGE_GL),
    },
    {
        "key": "TM", "id": "SNCFT-ANNABA", "file": "tunis-annaba", "public_code": "TM", "color": "#C62828",
        "name": ("Tunis – Annaba", "تونس – عنابة"),
        "long_name": ("Tunis – Béja – Jendouba – Ghardimaou – Souk Ahras – Annaba",
                      "تونس – باجة – جندوبة – غار الدماء – سوق أهراس – عنابة"),
        "src": ("gl", "Tunis-Béja-Jendouba-Ghardimaou (-Annaba)"),
        "gares": ("gl", "Tunis-Béja-Jendouba-Ghardimaou (-Annaba)"),
        # Gares algériennes hors du périmètre (lieux refusés hors de Tunisie) : le libellé de direction reste Annaba.
        "directions": [("ANNABA", "Tunis -> Annaba", "ANNABA", False),
                       ("TUNIS", "Annaba -> Tunis", "TUNIS-VILLE", True)],
        "headsign_override": {"ANNABA": ("Annaba", "عنابة")},
        "codes": {"A": _code([OUV, SAM, DIM], "Lundis, mercredis et vendredis seulement",
                             "أيام الإثنين و الأربعاء و الجمعة فقط"),
                  "B": _code([OUV, SAM, DIM], "Mardis, jeudis et dimanches seulement",
                             "أيام الثلاثاء و الخميس و الآحاد فقط")},
        "day_text": {"lundis, mercredis et vendredis": "A", "mardis, jeudis et dimanches": "B"},
        "day_filter": {"lundis, mercredis et vendredis": "MON,WED,FRI", "mardis, jeudis et dimanches": "TUE,THU,SUN"},
        "all_notes": ("intl", "Train international Tunis – Annaba : formalités frontalières et douanières à Ghardimaou. "
                              "Souk Ahras et Annaba (Algérie) ne sont pas représentées.",
                      "قطار دولي تونس – عنابة : إجراءات حدودية و ديوانية بغار الدماء"),
        "fare": None,
        "affiche": ("« Horaires des trains Grandes Lignes » Tunis – Ghardimaou – Annaba (trains TM1 et TM2), du "
                    "1er septembre 2026 au 30 juin 2027 sauf mois de Ramadan",
                    UP + "LTA-TUNIS-ANNABA-Hiver-2026.2027-1_page-0001-1-scaled.jpg", PAGE_GL),
    },
    {
        "key": "BIZERTE", "id": "SNCFT-BIZERTE", "file": "tunis-bizerte", "public_code": "1", "color": "#00838F",
        "name": ("Tunis – Bizerte", "تونس – بنزرت"),
        "long_name": ("Tunis – Manouba – Mateur – Tinja – Bizerte", "تونس – منوبة – ماطر – تينجة – بنزرت"),
        "src": ("gl", "Tunis-Mateur-Bizerte"), "gares": ("gl", "Tunis-Mateur-Bizerte"),
        "directions": [("BIZERTE", "Tunis -> Bizerte", "BIZERTE", False),
                       ("TUNIS", "Bizerte -> Tunis", "TUNIS-VILLE", True)],
        "codes": {"A": SAUF_DIM, "B": DIM_SEUL,
                  "C": _code([SAM, DIM], "Samedis, dimanches et fêtes", "أيام السبت و الآحاد و العطل الرسمية"),
                  "D": _code([OUV], "Du lundi au vendredi, sauf jours fériés",
                             "من الإثنين إلى الجمعة ما عدا العطل الرسمية")},
        "day_text": {"tous les jours sauf dimanches et fêtes": "A", "dimanches et fêtes": "B",
                     "samedis, dimanches et fêtes": "C", "du lundi au vendredi, sauf jours fériés": "D"},
        "fare": None,
        "affiche": ("« Horaires des trains Grandes Lignes » cartouche Tunis – Mateur – Bizerte, du 1er septembre 2026 "
                    "au 30 juin 2027 sauf mois de Ramadan",
                    UP + "LTA-TUNIS-ANNABA-Hiver-2026.2027-1_page-0001-1-scaled.jpg", PAGE_GL),
    },
    {
        "key": "L6", "id": "SNCFT-L6", "file": "ligne-6", "public_code": "6", "color": "#6D4C41",
        "name": ("Tunis – Le Kef / Kalaa Khasba", "تونس – الكاف / القلعة الخصبة"),
        "long_name": ("Tunis Ville – Gaafour – Dahmani – Le Kef – Kalaa Khasba",
                      "تونس – قعفور – الدهماني – الكاف – القلعة الخصبة"),
        "src": ("gl", "L6 Tunis-Gaafour-Dahmani-Le Kef/Kalaa Khasba"),
        "gares": ("gl", "L6 Tunis-Gaafour-Dahmani-Le Kef/Kalaa Khasba"),
        "directions": [("OUEST", "Tunis -> Le Kef / Kalaa Khasba", "KALAA-KHASBA", False),
                       ("TUNIS", "Kalaa Khasba / Le Kef -> Tunis", "TUNIS-VILLE", True)],
        "patterns": {
            "OUEST": [("OUEST-KALAA-KHASBA", L6_TRONC + L6_KK, True), ("OUEST-LE-KEF", L6_TRONC + ["LE-KEF"], False)],
            "TUNIS": [("NORD-KALAA-KHASBA", _rev(L6_TRONC + L6_KK), True),
                      ("NORD-LE-KEF", _rev(L6_TRONC + ["LE-KEF"]), False)],
        },
        "codes": {"-": TOUS, "A": SAUF_DIM, "B": DIM_SEUL},
        "day_text": {"tous les jours sauf dimanches et fêtes": "A", "dimanches et fêtes": "B"},
        # Trika (*) : « arrêt les dimanches et les mercredis seulement » → deux colonnes par train (avec / sans arrêt)
        "split_stop": ("TRIKA", "WED,SUN", "-WED,-SUN", (
            "trika", "Arrêt à Trika les dimanches et les mercredis seulement",
            "يتوقف بالتريكة أيام الآحاد و الأربعاء فقط")),
        "fare": None,
        "affiche": ("« Horaires des trains Grandes Lignes » ligne 6 Tunis – Gaafour – Dahmani – Le Kef – Kalaa Khasba, "
                    "du 1er septembre 2026 au 30 juin 2027 sauf mois de Ramadan",
                    UP + "L6-TUNIS-KALAA-KHASBA-Hiver-2026.2027-1_page-0001-1-scaled.jpg", PAGE_GL),
    },
    {
        "key": "NABEUL", "id": "SNCFT-NABEUL", "file": "banlieue-nabeul", "public_code": "BN", "color": "#33691E",
        "name": ("Banlieue de Nabeul", "أحواز نابل"),
        "long_name": ("Tunis / Borj Cédria – Nabeul", "تونس / برج السدرية – نابل"),
        "src": ("gl", "Banlieue de Nabeul"), "gares": ("gl", "Banlieue de Nabeul"),
        "directions": [("NABEUL", "Tunis / Borj Cédria -> Nabeul", "NABEUL", False),
                       ("TUNIS", "Nabeul -> Borj Cédria / Tunis", "TUNIS-VILLE", True)],
        "codes": {"-": TOUS}, "fare": None,
        "affiche": ("« Horaires des trains Grandes Lignes » ligne 5 page 2, cartouche Banlieue de Nabeul (codes de "
                    "jours non imprimés : circulation supposée quotidienne), du 1er septembre 2026 au 30 juin 2027 "
                    "sauf mois de Ramadan", UP + "L-5-TUNIS-TOZEUR-Hiver-2026-2027-1_page-0002-1-scaled.jpg", PAGE_GL),
    },
]

LINE_LABEL = {cfg["key"]: f"{cfg['name'][0]} ({cfg['public_code']})" for cfg in LINES}
LINE_LABEL["BANLIEUE-SUD"] = "Banlieue sud (A)"

# --- Tarifs -------------------------------------------------------------------------------------------------------
# Noms du GTFS SNCFT 2020-2021 → gare_id de doc/.
FARE_NAMES = {
    "Tunis Ville": "TUNIS-VILLE", "Djebal Jelloud": "JEBEL-JELLOUD", "Megrine Ryad": "MEGRINE-RIADH",
    "Megrine": "MEGRINE", "Sidi Rezig": "SIDI-REZIG", "Lycee Technique Rades": "LYCEE-RADES", "Rades": "RADES",
    "Rades Mel": "RADES-MELIANE", "Ez-Zahra": "EZZAHRA", "Ezzahra Lycée": "LYCEE-EZZAHRA", "Bou Kornine": "BOU-KORNINE",
    "Hammam Lif": "HAMMAM-LIF", "Arret Du Stade": "ARRET-DU-STADE", "Tahar Sfar": "TAHAR-SFAR",
    "Hammam Chat": "HAMMAM-CHATT", "Bir El Bey": "BIR-EL-BEY", "Borj Cedria": "BORJ-CEDRIA", "Erriadh": "ERRIADH",
    "Sousse Bab Jdid": "SOUSSE-BAB-JEDID", "Sousse Mohamed V": "SOUSSE-MOHAMED-V", "Sousse Sud": "SOUSSE-SUD",
    "Sousse Zone Industrielle": "SOUSSE-ZI", "Sahline Ville": "SAHLINE-VILLE", "Sahline Sebkha": "SAHLINE-SEBKHA",
    "Les Hotels Monastir": "LES-HOTELS", "Aeroport Skanes Monastir": "AEROPORT-MONASTIR", "La Faculte": "LA-FACULTE",
    "Monastir": "MONASTIR", "La Faculte 2": "LA-FACULTE-2", "Monastir Zone Industrielle": "MONASTIR-ZI",
    "Frina": "FRINA", "Khnis/Bembla": "KHNISS-BEMBLA", "Ksiba Bennane": "KSIBET-BENNANE", "Bouhjar": "BOUHJAR",
    "Lamta": "LAMTA", "Sayeda": "SAYADA", "Ksar Helal Zone Industrielle": "KSAR-HELLAL-ZI", "Ksar Helal": "KSAR-HELLAL",
    "Moknine Griba": "MOKNINE-GRIBAA", "Moknine Voyageurs": "MOKNINE", "Teboulba Zi": "TEBOULBA-ZI",
    "Teboulba": "TEBOULBA", "Bekalta": "BEKALTA", "Baghdedi": "BAGHDADI",
    # [I] doc/trains-banlieue/tarifs-et-abonnements.md : Mahdia Z.T. nommée « Mahdia Zone Industrielle » dans ce GTFS
    "Mahdia Zone Industrielle": "MAHDIA-ZT",
    "Sidi Masaoud": "SIDI-MESSAOUD", "Borj Arif": "BORJ-ARIF", "Mahdia Ezzahra": "MAHDIA-EZZAHRA", "Mahdia": "MAHDIA",
}
FARE_RELATIONS = {"Tunis_Ville-Erriadh": "BS", "Tunis_Ville-Haammam Lif": "BS", "Tunis_Ville-Rades": "BS",
                  "Sousse Bab Jdid-Mahdia": "SAHEL"}
FARE_GTFS_REF = ("GTFS SNCFT « Spring 2021 version D » (validité 2020-09-01 → 2021-06-30), fare_attributes.txt et "
                 "fare_rules.txt, transcrits dans doc/trains-banlieue/donnees/tarifs-banlieue-gtfs-2020-2021.csv")


class _Report:
    def __init__(self):
        self.written, self.removed, self.rejected, self.notes = [], [], [], []
        self.counts = dict()
        self.ids = dict()
        self.banlieue_sud = []

    def as_dict(self):
        return {"written": self.written, "removed": self.removed, "counts": dict(self.counts),
                "rejected": self.rejected, "notes": self.notes, "ids": dict(self.ids),
                "banlieue_sud": self.banlieue_sud}


def run(doc, src):
    doc, src = Path(doc), Path(src)
    rep = _Report()

    gares_rows = {"banlieue": read_csv(doc_path(doc, *GARES_BANLIEUE)), "gl": read_csv(doc_path(doc, *GARES_GL))}
    horaires = {"banlieue": read_csv(doc_path(doc, *HORAIRES_BANLIEUE)), "gl": read_csv(doc_path(doc, *HORAIRES_GL))}
    osm = _load_osm(doc)
    existing = _existing_places(src)

    gares, alias_of = _collect_gares(gares_rows, rep)
    place_of, new_places = _assign_places(gares, existing, osm, rep)
    for gid in alias_of:
        if alias_of[gid] in place_of:
            place_of[gid] = place_of[alias_of[gid]]
    for gid, pid in place_of.items():
        rep.ids[gid] = pid

    # Lignes (le contenu des lieux dépend des lignes qui les desservent : écrit après)
    owned_before = _owned_grid_dirs(src)
    served_by = defaultdict(list)
    built = []
    for cfg in LINES:
        built.append(_build_line(cfg, horaires, gares_rows, gares, alias_of, place_of, rep, served_by))

    # Lieux
    places_out = []
    for gid, place in new_places.items():
        lines = sorted(set(served_by.get(gid, [])), key=lambda k: [c["key"] for c in LINES + [{"key": "BANLIEUE-SUD"}]]
                       .index(k))
        if not lines:
            rep.rejected.append(f"Gare {gid} ({place['name']['fr']}) : desservie par aucun train de l'affiche — non créée")
            continue
        place["notes_internes"] = " ; ".join(filter(None, [
            place.pop("_internal"), "Lignes : " + ", ".join(LINE_LABEL[k] for k in lines)]))
        places_out.append(place)
    sources = f"{'/'.join(GARES_BANLIEUE)} et doc/{'/'.join(GARES_GL)}"
    rep.written.append(_w(write_yaml(src / PLACES_FILE, places_out, sources), src))
    rep.counts["gares"] = len(places_out)
    reused = sorted({place_of[g] for g in served_by} - {p["id"] for p in places_out})
    rep.counts["gares_reutilisees"] = len(reused)
    rep.notes.append(f"Gares existantes réutilisées (non redéfinies) : {', '.join(reused)}")

    # Lignes et grilles
    trips_total = 0
    for cfg, (line_yaml, grids, ntrips) in zip(LINES, built):
        rep.written.append(_w(write_yaml(src / NET_DIR / "lines" / f"{cfg['file']}.yaml", line_yaml,
                                         "/".join(HORAIRES_BANLIEUE if cfg["src"][0] == "banlieue" else HORAIRES_GL)),
                              src))
        for direction, text in grids.items():
            path = src / NET_DIR / "timetables" / cfg["file"] / VERSION / "NORMAL" / "TOUS" / f"{direction}.csv"
            rep.written.append(_w(write_text(path, text), src))
        trips_total += ntrips
    rep.counts["lignes"] = len(LINES)
    rep.counts["voyages"] = trips_total
    rep.counts["corrections"] = sum(len(b[0]["schedule"]["versions"][0].get("corrections", [])) for b in built)

    # Tarifs
    _fares(doc, src, place_of, rep, {g for g, keys in served_by.items() if "SAHEL" in keys})

    # Nettoyage : fichiers générés devenus inutiles (jamais un fichier saisi à la main)
    _cleanup(src, rep, owned_before)

    # Banlieue sud : comparaison de la grille saisie à la main avec doc/ (lecture seule)
    _compare_banlieue_sud(src, horaires["banlieue"], gares, rep)

    rep.notes.append("Codes de jours : affiches de Tunis (E, D) → « - » tous les jours, A [OUVRABLE, SAMEDI], "
                     "B [DIMANCHE] comme banlieue-sud.yaml ; un jour férié roule comme un dimanche (network.yaml). "
                     "Métro du Sahel, banlieue de Nabeul, Redeyef et trains des grandes lignes sans lettre : aucun code "
                     "imprimé → « - » tous les jours ([I] doc/). Ligne 5 : la lettre (A) a deux sens selon la page "
                     "(aller : sauf samedis et veilles de fêtes → A [OUVRABLE, DIMANCHE] ; retour : sauf dimanches et "
                     "fêtes → clé A2 [OUVRABLE, SAMEDI]). Les « veilles de fêtes » ne sont pas modélisables : le "
                     "5-12/79 est proposé ces jours-là (le libellé du code le précise). Tunis – Annaba : codes A/B "
                     "+ @days MON,WED,FRI / TUE,THU,SUN.")
    rep.notes.append("Ligne 6, Trika « arrêt les dimanches et les mercredis seulement » : chaque train qui la dessert "
                     "(6/51, 6/65, 6/50, 6/76) est écrit en deux colonnes — « 6/51 » (@days -WED,-SUN, Trika « | ») "
                     "et « 6/51* » (@days WED,SUN, arrêt à Trika), avec un renvoi « trika ».")
    rep.notes.append("Tunis – Annaba (TM1/TM2, code TM) : ligne distincte de Tunis – Ghardimaou, limitée à Tunis, Béja, "
                     "Jendouba, Ghardimaou (arrivée/départ de l'arrêt frontalier conservés), libellé de direction "
                     "« Annaba » et renvoi « intl » ; l'usage du train pour un trajet intérieur (Tunis – Béja…) "
                     "n'est pas confirmé par doc/.")
    rep.notes.append("Codes publics : E, D (RFR), MS (métro du Sahel), BN (banlieue de Nabeul), 5 et 6 (lignes 5 et 6 "
                     "des affiches L-5 / L6), TA (Tunis – Ghardimaou, affiche LTA), TM (trains TM1/TM2 Tunis – Annaba), "
                     "1 (Tunis – Bizerte : trains 1/4, 1/10, 1/19, 1/25 = ligne SNCFT 1), RM (Redeyef – Moularès – "
                     "Métlaoui : trains 16/70 et 15/77 sur deux numéros de ligne). Aucun ne vaut « A ».")
    rep.notes.append("Ramadan : aucune grille de Ramadan (affiches « sauf mois de Ramadan », horaires spéciaux non "
                     "publiés) ; pendant le Ramadan 2027, le réseau retombe sur la grille NORMAL (repli RAMADAN → NORMAL "
                     "de network.yaml), signalé comme repli dans le rapport de build.")
    return rep.as_dict()


# --- Lecture --------------------------------------------------------------------------------------------------------

def _w(path, src):
    return Path(path).relative_to(src.parent.parent).as_posix()


def _load_osm(doc):
    try:
        data = json.loads(doc_path(doc, *OSM_STATIONS).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    out = []
    for f in data.get("features", []):
        if f.get("geometry", {}).get("type") != "Point":
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        props = f.get("properties", {})
        out.append({"id": f.get("id"), "lat": lat, "lon": lon, "props": props,
                    "preferred": props.get("railway") in ("station", "halt")
                    and props.get("public_transport") != "stop_position"})
    return out


def _nearest_osm(osm, lat, lon, within_m):
    best = None
    for f in osm:
        d = dist_m((lat, lon), (f["lat"], f["lon"]))
        if d <= within_m:
            key = (not f["preferred"], round(d, 1), f["id"] or "")
            if best is None or key < best[0]:
                best = (key, f, d)
    return (best[1], best[2]) if best else (None, None)


def _existing_places(src):
    """Lieux définis hors de mes fichiers (saisis à la main ou générés par d'autres importeurs) : jamais redéfinis."""
    out = {}
    own = (src / PLACES_FILE).resolve()
    for path in sorted((src / "places").rglob("*.yaml")):
        if path.name == "hubs.yaml" or path.resolve() == own or "sncft" in path.relative_to(src / "places").parts[:1]:
            continue
        try:
            data = read_yaml(path) or []
        except Exception:  # fichier en cours d'écriture par un autre importeur : ignoré
            continue
        for p in data if isinstance(data, list) else []:
            if isinstance(p, dict) and p.get("id"):
                out[p["id"]] = {**p, "_file": path.relative_to(src).as_posix(), "_hand": not is_generated(path)}
    return out


def _collect_gares(gares_rows, rep):
    """Une entrée par gare_id de doc/ (les deux CSV partagent leurs identifiants), puis fusion des doublons proches."""
    gares = dict()
    for origin in ("banlieue", "gl"):
        for r in gares_rows[origin]:
            gid = r["gare_id"]
            g = gares.get(gid)
            lat = float(r["lat"]) if r["lat"] else None
            lon = float(r["lon"]) if r["lon"] else None
            if g is None:
                gares[gid] = g = {"gare_id": gid, "nom_fr": r["nom_fr"], "nom_ar": clean_ar(r["nom_ar"]),
                                  "code": r["code_sncft"], "lat": lat, "lon": lon, "source": r["source_coord"],
                                  "id_app": r.get("id_app", ""), "notes": [], "alt_names": []}
            else:
                if r["nom_fr"] and norm_name(r["nom_fr"]) != norm_name(g["nom_fr"]):
                    g["alt_names"].append(r["nom_fr"])
                if not g["code"] and r["code_sncft"]:
                    g["code"] = r["code_sncft"]
                if not g["id_app"] and r.get("id_app"):
                    g["id_app"] = r["id_app"]
                if lat is not None and g["lat"] is not None and dist_m((lat, lon), (g["lat"], g["lon"])) > 50:
                    rep.notes.append(f"Gare {gid} : deux positions à {dist_m((lat, lon), (g['lat'], g['lon'])):.0f} m "
                                     f"dans doc/ ; première retenue ({g['source']})")
            if r.get("note") and r["note"] not in g["notes"]:
                g["notes"].append(r["note"])

    # Même gare sous deux identifiants (ex. MANNOUBA de la ligne D = MANOUBA des grandes lignes, à 5 m)
    alias_of = {}
    ids = [g for g in gares.values() if g["lat"] is not None]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if a["gare_id"] in alias_of or b["gare_id"] in alias_of:
                continue
            d = dist_m((a["lat"], a["lon"]), (b["lat"], b["lon"]))
            if d <= 50:
                keep, drop = (b, a) if (b["code"] and not a["code"]) else (a, b)
                alias_of[drop["gare_id"]] = keep["gare_id"]
                if norm_name(drop["nom_fr"]) != norm_name(keep["nom_fr"]):
                    keep["alt_names"].append(drop["nom_fr"])
                keep["alt_names"] += drop["alt_names"]
                rep.notes.append(f"Gares {drop['gare_id']} et {keep['gare_id']} de doc/ fusionnées ({d:.0f} m : même "
                                 f"gare, « {drop['nom_fr']} » sur l'affiche de la ligne D)")
    for gid in alias_of:
        del gares[gid]
    return gares, alias_of


def _display_name(g):
    if g["gare_id"] in DISPLAY_NAMES:
        fr, ar = DISPLAY_NAMES[g["gare_id"]]
        return fr, ar, []
    fr = g["nom_fr"]
    aliases = []
    m = re.fullmatch(r"(.+?)\s*\((.+)\)", fr)
    if m:
        fr = m.group(1).strip()
        aliases.append(m.group(2).strip())
    return fr, g["nom_ar"], aliases


def _aliases(g, fr, extra, osm_feat):
    out, seen = [], {norm_name(fr)}
    candidates = list(extra) + g["alt_names"] + EXTRA_ALIASES.get(g["gare_id"], [])
    for note in g["notes"]:
        candidates += re.findall(r"«\s*([^»]+?)\s*»\s*(?:sans code\s+)?(?:dans les données|sur l.affiche)", note)
    if osm_feat:
        candidates += [osm_feat["props"].get("name:fr", ""), osm_feat["props"].get("name", "")]
    for name in ("Zone industrielle", "Zone touristique"):
        if name in g["nom_fr"]:
            short = "Z.I." if name == "Zone industrielle" else "Z.T."
            candidates.append(g["nom_fr"].replace(name, short))
            candidates.append(g["nom_fr"].replace(name, short.replace(".", "")))
    for c in candidates:
        c = c.strip()
        if not c:
            continue
        is_ar = bool(re.search(r"[؀-ۿ]", c))
        key = clean_ar(c) if is_ar else norm_name(c)
        if not key or key in seen or (is_ar and key == g["nom_ar"]):
            continue
        seen.add(key)
        out.append(clean_ar(c) if is_ar else c.lower())
    return out


def _coord_provenance(g, osm):
    """(source, ref, info interne) selon l'origine des coordonnées."""
    src = g["source"]
    code = f", code SNCFT {g['code']}" if g["code"] else ""
    names = "noms FR/AR : affiches SNCFT hiver 2026-2027"
    if src.startswith("data.transport.tn"):
        kind = src[len("data.transport.tn"):].strip().lower() or "grandes lignes"
        dataset = DTT_SETS.get(kind, DTT_SETS["grandes lignes"])
        return "OFFICIEL", f"data.transport.tn, jeu {dataset}{code} ; {names}"
    if src.startswith("OSM"):
        feat, d = _nearest_osm(osm, g["lat"], g["lon"], 30)
        ref = f"{feat['id']} (extrait Geofabrik du 2026-10-13)" if feat else "OpenStreetMap (extrait Geofabrik du 2026-10-13)"
        return "OSM", f"{ref} ; {names}"
    if src.startswith("GTFS SNCFT"):
        return "OFFICIEL", f"GTFS SNCFT 2020-2021 (« Spring 2021 version D »), stops.txt{code} ; {names}"
    raise RuntimeError(f"Source de coordonnées inconnue pour {g['gare_id']} : {src!r}")


def _assign_places(gares, existing, osm, rep):
    """gare_id → id du lieu ; crée les lieux absents de data/src (jamais ceux déjà définis ailleurs)."""
    place_of, new_places = dict(), dict()
    trn_existing = {pid: p for pid, p in existing.items() if pid.startswith("TRN-") and p.get("kind") == "station"}
    for gid, g in gares.items():
        if g["lat"] is None:
            continue   # signalé à la construction des lignes (gare écartée du parcours)
        if not in_tunisia(g["lat"], g["lon"]):
            rep.rejected.append(f"Gare {gid} : hors de Tunisie ({g['lat']}, {g['lon']})")
            continue
        candidate = g["id_app"] or "TRN-" + gid.replace("-", "")
        if candidate in existing:
            p = existing[candidate]
            d = dist_m((g["lat"], g["lon"]), (p["lat"], p["lon"]))
            if d > 1000:
                raise RuntimeError(f"{candidate} existe déjà ({p['_file']}) à {d:.0f} m de la gare {gid} de doc/")
            place_of[gid] = candidate
            if d > 150:
                rep.notes.append(f"Gare {gid} : le lieu existant {candidate} ({p['_file']}) est à {d:.0f} m de la "
                                 f"position de doc/ ({g['source']}) — lieu existant conservé, à vérifier sur place")
            continue
        near = [(dist_m((g["lat"], g["lon"]), (p["lat"], p["lon"])), pid) for pid, p in trn_existing.items()]
        near = sorted(x for x in near if x[0] <= 100)
        if near:
            place_of[gid] = near[0][1]
            rep.notes.append(f"Gare {gid} rattachée au lieu existant {near[0][1]} ({near[0][0]:.0f} m)")
            continue
        fr, ar, extra = _display_name(g)
        if not ar:
            rep.rejected.append(f"Gare {gid} ({fr}) : nom arabe manquant — non créée")
            continue
        source, ref = _coord_provenance(g, osm)
        feat, d = _nearest_osm(osm, g["lat"], g["lon"], 150)
        internal = [f"Code SNCFT {g['code']}" if g["code"] else ""]
        if source != "OSM" and feat:
            internal.append(f"OSM {feat['id']} à {d:.0f} m")
        internal += g["notes"]
        place = _od([("id", candidate), ("kind", "station"), ("name", i18n(fr, ar)),
            ("aliases", _aliases(g, fr, extra, feat if feat and d <= 100 else None)),
            ("lat", round(g["lat"], 6)), ("lon", round(g["lon"], 6)), ("status", "active"),
            ("provenance", prov(source, ref)), ("_internal", " ; ".join(x for x in internal if x)),
        ])
        if not place["aliases"]:
            del place["aliases"]
        if candidate in {p["id"] for p in new_places.values()}:
            raise RuntimeError(f"Identifiant {candidate} attribué deux fois")
        new_places[gid] = place
        place_of[gid] = candidate
    return place_of, new_places


# --- Lignes ---------------------------------------------------------------------------------------------------------

def _trains(rows, ligne):
    """Trains d'une ligne de doc/ : { sens: dict(train → [lignes du CSV triées par ordre]) }."""
    out = defaultdict(dict)
    for r in rows:
        if r["ligne"] != ligne:
            continue
        out[r["sens"]].setdefault(r["train"], []).append(r)
    for sens in out:
        for train in out[sens]:
            out[sens][train].sort(key=lambda r: int(r["ordre"]))
    return out


def _calls(rows):
    """[(gare_id, arrivée, départ, ligne CSV)] ; arrivée + départ consécutifs fusionnés ; passage de minuit → 24:xx."""
    calls, offset, last = [], 0, None
    for r in rows:
        t = minutes(r["heure"])
        if last is not None and t + offset < last:
            offset += 24 * 60
        t += offset
        last = t
        if calls and r["type"] == "depart" and calls[-1][0] == r["gare_id"] and calls[-1][3]["type"] == "arrivee":
            calls[-1] = (r["gare_id"], calls[-1][1], t, r)
        else:
            calls.append((r["gare_id"], t, t, r))
    return calls


def _subseq_positions(seq, pattern):
    pos, out = -1, []
    for x in seq:
        try:
            pos = pattern.index(x, pos + 1)
        except ValueError:
            return None
        out.append(pos)
    return out


def _cell(arr, dep):
    return hhmm(arr) if arr == dep else f"{hhmm(arr)}/{hhmm(dep)}"


def _build_line(cfg, horaires, gares_rows, gares, alias_of, place_of, rep, served_by):
    key = cfg["key"]
    src_kind, ligne = cfg["src"]
    trains = _trains(horaires[src_kind], ligne)
    order = [alias_of.get(r["gare_id"], r["gare_id"]) for r in gares_rows[cfg["gares"][0]]
             if r["ligne"] == cfg["gares"][1]]
    order = list(dict.fromkeys(order))
    codes_used, notes_used, corrections = dict(), dict(), []
    directions, patterns, grids = [], [], dict()
    missing_reported = set()
    ntrips = 0
    per_direction = {}

    for direction, sens, head_gid, reverse in cfg["directions"]:
        if sens not in trains:
            raise RuntimeError(f"{key} : sens « {sens} » absent de doc/")
        rows_order = list(reversed(order)) if reverse else list(order)
        columns = []   # (en-tête, code, @days, [notes], {index de ligne: cellule}, parcours)
        dir_trains = []
        for train, rows in trains[sens].items():
            calls = []
            for gid, arr, dep, r in _calls(rows):
                gid = alias_of.get(gid, gid)
                if gid not in place_of:
                    missing_reported.add((gid, train))
                    continue
                calls.append((gid, arr, dep, r))
            if len(calls) < 2:
                rep.rejected.append(f"{LINE_LABEL[key]} : train {train} écarté (moins de 2 gares localisées)")
                continue
            dir_trains.append((train, rows, calls))

        served = {c[0] for _, _, calls in dir_trains for c in calls}
        rows_order = [g for g in rows_order if g in served]
        dir_patterns = cfg.get("patterns", {}).get(direction)
        if dir_patterns:
            pats = [(pid, [g for g in stops if g in place_of], main) for pid, stops, main in dir_patterns]
        else:
            pats = [(direction, rows_order, True)]

        for train, rows, calls in dir_trains:
            seq = [c[0] for c in calls]
            idx = _subseq_positions(seq, rows_order)
            if idx is None and len(dir_trains) == 1:
                rows_order = seq[:]       # gare desservie deux fois (Tabeddit) : ordre du train lui-même
                pats = [(direction, rows_order, True)]
                idx = list(range(len(seq)))
            if idx is None:
                raise RuntimeError(f"{key} {direction} : le train {train} ne suit pas l'ordre des gares de doc/")
            match = next(((pid, stops) for pid, stops, _ in pats if _subseq_positions(seq, stops) is not None), None)
            if match is None:
                raise RuntimeError(f"{key} {direction} : le train {train} ne suit aucun parcours ({seq})")
            pat_stops = set(match[1])
            cells = {}
            for (gid, arr, dep, r), i in zip(calls, idx):
                cells[i] = _cell(arr, dep)
            for i in range(idx[0] + 1, idx[-1]):
                if i not in cells and rows_order[i] in pat_stops:
                    cells[i] = "|"

            jours = rows[0].get("jours", "")
            notes = []
            day_filter = ""
            if src_kind == "banlieue":
                code = jours or "-"
                if not jours and key != "SAHEL":
                    rep.notes.append(f"{LINE_LABEL[key]} : train {train} sans code de jours sur l'affiche (case vide) "
                                     f"— compté « tous les jours » ([I] doc/)")
            else:
                if jours and jours not in cfg.get("day_text", {}):
                    raise RuntimeError(f"{key} : jours « {jours} » (train {train}) non traduits")
                code = cfg.get("day_text", {}).get(jours, "-") if jours else "-"
                day_filter = cfg.get("day_filter", {}).get(jours, "")
                if jours in cfg.get("text_notes", {}):
                    notes.append(cfg["text_notes"][jours])
            if cfg.get("all_notes"):
                notes.append(cfg["all_notes"])
            for gid_missing, note in cfg.get("missing_stop_notes", {}).items():
                if any(alias_of.get(r["gare_id"], r["gare_id"]) == gid_missing for r in rows):
                    notes.append(note)
            if code not in cfg["codes"]:
                raise RuntimeError(f"{key} : code de jours « {code} » non défini (train {train})")
            codes_used[code] = cfg["codes"][code]
            for n in notes:
                notes_used[n[0]] = n

            for (gid, arr, dep, r), i in zip(calls, idx):
                served_by[gid].append(key)
                if r["statut"] == "I":
                    m = re.search(r"imprimé (\S+) \(coquille\)", r.get("note", ""))
                    if m:
                        why = re.search(r"\((entre [^)]*)\)", r["note"])
                        corrections.append({
                            "direction": direction, "train": train, "stop": place_of[gid], "printed": m.group(1),
                            "corrected": _cell(arr, dep),
                            "reason": (why.group(1).capitalize() + " (gares voisines)") if why
                            else "Valeur corrigée par cohérence avec les gares voisines"})

            split = cfg.get("split_stop")
            if split and split[0] in seq:
                stop_gid, days_with, days_without, note = split
                notes_used[note[0]] = note
                i_split = idx[seq.index(stop_gid)]
                without = dict(cells)
                without[i_split] = "|"
                columns.append((train, code, days_without, notes + [note], without))
                columns.append((train + "*", code, days_with, notes + [note], cells))
            else:
                columns.append((train, code, day_filter, notes, cells))

        # Grille CSV
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["stop_id"] + [c[0] for c in columns])
        w.writerow(["@jours"] + [c[1] for c in columns])
        if any(c[2] for c in columns):
            w.writerow(["@days"] + [c[2] for c in columns])
        if any(c[3] for c in columns):
            w.writerow(["@notes"] + [" ".join(n[0] for n in c[3]) for c in columns])
        for i, gid in enumerate(rows_order):
            w.writerow([place_of[gid]] + [c[4].get(i, "") for c in columns])
        grids[direction] = out.getvalue()
        ntrips += len(columns)
        per_direction[direction] = len(columns)

        if head_gid in place_of:
            head = gares[head_gid]
            fr, ar, _ = _display_name(head)
            headsign = {"fr": fr, "ar": ar}
        else:
            fr, ar = cfg.get("headsign_override", {}).get(direction) or (None, None)
            if fr is None:
                g = next(r for r in gares_rows[cfg["gares"][0]] if r["gare_id"] == head_gid)
                fr, ar = g["nom_fr"], clean_ar(g["nom_ar"])
            headsign = {"fr": fr, "ar": ar}
        directions.append({"id": direction, "headsign": headsign})
        for pid, stops, main in pats:
            used_stops = [place_of[g] for g in stops]
            patterns.append(_od([("id", pid), ("direction", direction), ("main", main),
                                         ("stops", used_stops), ("shape", "auto")]))

    missing = sorted({gid for gid, _ in missing_reported})
    for gid in missing:
        trains_list = sorted({t for g, t in missing_reported if g == gid})
        rep.rejected.append(f"{LINE_LABEL[key]} : gare {gid} retirée des parcours ({len(trains_list)} train(s)) — "
                            f"{_why_missing(gid, gares, alias_of)}")

    ratio = contrast_ratio(cfg["color"], "#FFFFFF")
    if ratio < 4.5:
        raise RuntimeError(f"{key} : contraste {ratio:.1f} < 4,5")

    title, url, page = cfg["affiche"]
    csv_src = "/".join(HORAIRES_BANLIEUE if src_kind == "banlieue" else HORAIRES_GL)
    version = _od([("id", VERSION), ("valid_from", VALID_FROM), ("valid_to", VALID_TO),
        ("provenance", prov("OFFICIEL", f"Affiche SNCFT {title} ({url}), page {page} consultée le 2026-10-14 ; "
                                        f"transcription doc/{csv_src}")),
    ])
    if corrections:
        version["corrections"] = corrections
    line = _od([("id", cfg["id"]), ("network", NETWORK), ("mode", "TRAIN"), ("public_code", cfg["public_code"]),
        ("name", i18n(*cfg["name"])), ("long_name", i18n(*cfg["long_name"])),
        ("color", cfg["color"]), ("text_color", "#FFFFFF"), ("status", "active"),
        ("directions", directions), ("patterns", patterns),
    ])
    if notes_used:
        line["notes"] = dict((k, {"fr": fr, "ar": ar}) for k, fr, ar in notes_used.values())
    line["day_codes"] = {k: v for k, v in cfg["codes"].items() if k in codes_used}
    line["schedule"] = _od([("kind", "timetable"), ("source_dir", f"timetables/{cfg['file']}"),
                                    ("fallback", "inherit"), ("versions", [version])])
    if cfg.get("fare"):
        line["fare"] = cfg["fare"]
    line["provenance"] = prov("OFFICIEL", f"{page} — affiche hiver 2026-2027 ({url})")
    rep.notes.append(f"{LINE_LABEL[key]} : {ntrips} voyage(s) ("
                     + ", ".join(f"{d} {n}" for d, n in per_direction.items()) + ")"
                     + (f", {len(corrections)} coquille(s) corrigée(s)" if corrections else ""))
    return line, grids, ntrips


def _why_missing(gid, gares, alias_of):
    if gid in ("SOUK-AHRAS", "ANNABA"):
        return "gare algérienne, hors du périmètre des lieux (Tunisie seulement)"
    if gid == "EL-OUEDIANE":
        return ("coordonnées inconnues (absente de data.transport.tn et d'OSM ; peut-être la gare de Degache, 552G, "
                "non confirmé)")
    if gid == "GOBAA-VILLE":
        return "coordonnées inconnues (absente d'OSM et de data.transport.tn ; « Gobâa 2 » de Wikipédia ?)"
    return "gare sans lieu (coordonnées absentes ou nom arabe manquant)"


# --- Tarifs ---------------------------------------------------------------------------------------------------------

def _fares(doc, src, place_of, rep, sahel_gids):
    rows = read_csv(doc_path(doc, *TARIFS_BANLIEUE))
    by_pair = defaultdict(set)
    group = {}
    unknown = set()
    for r in rows:
        a, b = FARE_NAMES.get(r["origine"]), FARE_NAMES.get(r["destination"])
        if a is None or b is None:
            unknown.add(r["origine"] if a is None else r["destination"])
            continue
        by_pair[(a, b)].add(dt_to_millimes(r["prix_DT_plein"]))
        group[(a, b)] = FARE_RELATIONS[r["relation_gtfs"]]
    for name in sorted(unknown):
        rep.rejected.append(f"Tarifs 2020-2021 : gare « {name} » inconnue — couples ignorés")

    pairs = {"BS": [], "SAHEL": []}
    dropped = []
    for (a, b), prices in by_pair.items():
        if a == b:
            dropped.append(f"{a} → {b} (même gare)")
            continue
        reverse = by_pair.get((b, a))
        if len(prices) > 1:
            dropped.append(f"{a} → {b} (deux prix : {', '.join(_dt(p) for p in sorted(prices))})")
            continue
        if reverse is not None and reverse != prices:
            dropped.append(f"{a} → {b} ({_dt(next(iter(prices)))}, contredit par le sens inverse "
                           f"{'/'.join(_dt(p) for p in sorted(reverse))})")
            continue
        if a not in place_of or b not in place_of:
            dropped.append(f"{a} → {b} (gare sans lieu)")
            continue
        pairs[group[(a, b)]].append((a, b, next(iter(prices))))
    for d in sorted(dropped):
        rep.rejected.append(f"Tarifs 2020-2021 : couple {d} écarté")
    for grp, label in (("BS", "banlieue sud"), ("SAHEL", "Sahel")):
        stops = sorted({g for (a, b), gr in group.items() if gr == grp for g in (a, b)})
        kept = {(a, b) for a, b, _ in pairs[grp]}
        absent = [f"{a} → {b}" for a in stops for b in stops if a != b and (a, b) not in kept
                  and (a, b) not in by_pair]
        if absent:
            rep.rejected.append(f"Tarifs 2020-2021 ({label}) : {len(absent)} couple(s) absent(s) du GTFS ({', '.join(absent)}) "
                                f"— le back-end affichera le prix maximal de la ligne, signalé « environ »")

    ref_gtfs = (f"Dernier tarif connu : {FARE_GTFS_REF} ; tarif en vigueur non publié (recherches du 2026-10-14)")
    order = {g: i for i, g in enumerate(place_of)}
    written = 0
    # Banlieue sud : FARE-SNCFT-A, référencé par banlieue-sud.yaml (saisi à la main), remplacé s'il est généré
    path_a = src / NET_DIR / "fares" / "fare-sncft-a.yaml"
    if path_a.exists() and not is_generated(path_a):
        rep.rejected.append("Tarif banlieue sud : networks/sncft/fares/fare-sncft-a.yaml a été saisi à la main — non "
                            "remplacé (paires 2020-2021 disponibles dans doc/)")
    else:
        rep.written.append(_w(write_yaml(path_a, _od_fare("FARE-SNCFT-A", pairs["BS"], place_of, order, ref_gtfs),
                                         "/".join(TARIFS_BANLIEUE)), src))
        rep.notes.append(f"Tarif FARE-SNCFT-A (banlieue sud) : tarif de test 0,800 DT remplacé par {len(pairs['BS'])} "
                         f"couples 2020-2021 (0,450 – 0,800 DT), en ESTIMATION")
        written += 1
    rep.written.append(_w(write_yaml(src / NET_DIR / "fares" / "fare-sncft-sahel.yaml",
                                     _od_fare("FARE-SNCFT-SAHEL", pairs["SAHEL"], place_of, order, ref_gtfs),
                                     "/".join(TARIFS_BANLIEUE)), src))
    written += 1
    rep.written.append(_w(write_yaml(src / NET_DIR / "fares" / "fare-sncft-e.yaml", _od([("id", "FARE-SNCFT-E"), ("model", "flat"), ("currency", "TND"), ("categories", ["PLEIN"]),
        ("versions", [_od([("valid_from", "2023-03-27"), ("price_millimes", {"PLEIN": 700})])]),
        ("provenance", prov("ESTIMATION", "Dernier tarif connu : 0,700 DT, tarif unique de la ligne E depuis le "
                                          "2023-03-27 (communiqué SNCFT relayé par Webdo, 2023, voir "
                                          "doc/trains-banlieue/tarifs-et-abonnements.md) ; tarif en vigueur non "
                                          "publié")),
    ]), "trains-banlieue/tarifs-et-abonnements.md"), src))
    written += 1
    rep.counts["tarifs"] = written
    rep.counts["paires_tarifaires"] = len(pairs["BS"]) + len(pairs["SAHEL"])

    for g in (g for g in sorted(sahel_gids) if not any(g in (a, b) for a, b, _ in pairs["SAHEL"])):
        rep.rejected.append(f"Tarifs 2020-2021 : aucune paire pour {g} (absente du GTFS) — le back-end affichera le "
                            f"prix maximal de la ligne, signalé « environ »")
    rep.notes.append("Tarif Sahel : « Mahdia Zone Industrielle » du GTFS 2020-2021 rattachée à Mahdia Zone touristique "
                     "(même rang dans l'ordre des gares, [I] doc/trains-banlieue/tarifs-et-abonnements.md)")
    rep.rejected.append("Tarif ligne D : aucun tarif connu — pas de tarif (avertissement FARE_MISSING attendu)")
    rep.rejected.append("Tarifs grandes lignes (Seat61, non datés : Tunis – Sousse 7,600 DT, Monastir 9,200, Sfax "
                        "12,400, Gabès 18,200 en 2e classe) : non importés — source non officielle et non datée, et "
                        "un tarif od_pairs à 4 relations ferait afficher le prix maximal (18,200 DT) pour toute autre "
                        "relation de la ligne 5")
    rep.rejected.append("Tarif Tunis – Annaba (38,000 DT en 2e classe, SNCFT 2024) : non importé — Annaba n'est pas un "
                        "lieu (hors de Tunisie) et un prix unique sur la ligne TM vaudrait aussi pour Tunis – Béja")


def _dt(millimes):
    return f"{millimes // 1000},{millimes % 1000:03d}"


def _od_fare(fid, pairs, place_of, order, ref):
    pairs = sorted(pairs, key=lambda p: (order[p[0]], order[p[1]]))
    return _od([("id", fid), ("model", "od_pairs"), ("currency", "TND"), ("categories", ["PLEIN"]),
        ("versions", [_od([("valid_from", "2020-09-01"), ("pairs", [
            _od([("from", place_of[a]), ("to", place_of[b]), ("price_millimes", {"PLEIN": p})])
            for a, b, p in pairs])])]),
        ("provenance", prov("ESTIMATION", ref)),
    ])


# --- Nettoyage ------------------------------------------------------------------------------------------------------

def _owned_grid_dirs(src):
    """Dossiers de grilles des lignes générées (avant écriture) : seuls endroits où des CSV peuvent être retirés."""
    owned = set()
    lines_dir = src / NET_DIR / "lines"
    for path in sorted(lines_dir.glob("*.yaml")) if lines_dir.exists() else []:
        if not is_generated(path):
            continue
        try:
            data = read_yaml(path) or {}
        except Exception:
            continue
        sd = (data.get("schedule") or {}).get("source_dir")
        if sd:
            owned.add(sd)
    return owned


def _cleanup(src, rep, owned_before):
    written = {(src.parent.parent / p).resolve() for p in rep.written}
    hand_dirs = set()
    for path in sorted((src / NET_DIR / "lines").glob("*.yaml")):
        if not is_generated(path):
            sd = ((read_yaml(path) or {}).get("schedule") or {}).get("source_dir")
            if sd:
                hand_dirs.add(sd)
    # YAML générés (lignes, tarifs, lieux SNCFT) qui ne sont plus produits
    for folder in (src / NET_DIR / "lines", src / NET_DIR / "fares", src / "places" / "sncft"):
        for path in sorted(folder.glob("*.yaml")) if folder.exists() else []:
            if path.resolve() not in written and remove_generated(path):
                rep.removed.append(_w(path, src))
    # Grilles CSV : uniquement dans les dossiers des lignes générées (jamais ceux d'une ligne saisie à la main)
    owned = (owned_before | {f"timetables/{c['file']}" for c in LINES}) - hand_dirs
    for sd in sorted(owned):
        base = src / NET_DIR / sd
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in (".csv", ".yaml") and path.resolve() not in written:
                path.unlink()
                rep.removed.append(_w(path, src))
        for d in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        if not any(base.iterdir()):
            base.rmdir()


# --- Banlieue sud : comparaison avec la grille saisie à la main -----------------------------------------------------

def _read_hand_grid(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = [[c.strip() for c in r] for r in csv.reader(f) if any(c.strip() for c in r)]
    trains = rows[0][1:]
    codes = {}
    served = {t: {} for t in trains}
    for row in rows[1:]:
        row = row + [""] * (len(trains) + 1 - len(row))
        if row[0] == "@jours":
            codes = dict(zip(trains, row[1:]))
        elif not row[0].startswith("@"):
            for t, cell in zip(trains, row[1:]):
                if cell and cell != "|":
                    served[t][row[0]] = cell
    return trains, codes, served


def _compare_banlieue_sud(src, horaires, gares, rep):
    grids = {"SUD": "Tunis Ville -> Erriadh", "NORD": "Erriadh -> Tunis Ville"}
    app_id = {gid: g["id_app"] for gid, g in gares.items() if g["id_app"]}
    trains = _trains(horaires, "BANLIEUE-SUD")
    diffs = []
    n_trains = n_cells = 0
    for direction, sens in grids.items():
        path = src / HAND_GRIDS / f"{direction}.csv"
        if not path.exists():
            diffs.append(f"{direction} : grille saisie absente ({path.relative_to(src).as_posix()})")
            continue
        hand_trains, hand_codes, hand_served = _read_hand_grid(path)
        doc_trains = trains[sens]
        for t in doc_trains:
            if t not in hand_served:
                diffs.append(f"{direction} : train {t} présent dans doc/, absent de la grille saisie")
        for t in hand_trains:
            if t not in doc_trains:
                diffs.append(f"{direction} : train {t} présent dans la grille saisie, absent de doc/")
        for t, rows in doc_trains.items():
            if t not in hand_served:
                continue
            n_trains += 1
            code = rows[0]["jours"] or "(vide)"
            if hand_codes.get(t, "") != rows[0]["jours"]:
                diffs.append(f"{direction} train {t} : code de jours saisi « {hand_codes.get(t, '')} », doc/ « {code} »")
            doc_cells = {app_id.get(gid, gid): _cell(arr, dep) for gid, arr, dep, _ in _calls(rows)}
            n_cells += len(doc_cells)
            for stop in sorted(set(doc_cells) | set(hand_served[t])):
                a, b = hand_served[t].get(stop), doc_cells.get(stop)
                if a != b:
                    diffs.append(f"{direction} train {t} à {stop} : saisi « {a or 'non desservi'} », "
                                 f"doc/ « {b or 'non desservi'} »")
    # Corrections déclarées dans la ligne saisie ↔ coquilles de doc/
    try:
        hand_line = read_yaml(src / HAND_LINE)
        hand_corr = {(c["train"], c["stop"], c["printed"], c["corrected"])
                     for v in hand_line["schedule"]["versions"] for c in v.get("corrections", [])}
    except Exception:
        hand_corr = set()
    doc_corr = set()
    for sens in grids.values():
        for t, rows in trains[sens].items():
            for r in rows:
                m = re.search(r"imprimé (\S+) \(coquille\)", r.get("note", ""))
                if r["statut"] == "I" and m:
                    doc_corr.add((t, app_id.get(r["gare_id"], r["gare_id"]), m.group(1), r["heure"]))
    for c in sorted(doc_corr - hand_corr):
        diffs.append(f"Coquille de doc/ absente des corrections saisies : train {c[0]} à {c[1]}, imprimé {c[2]} → {c[3]}")
    for c in sorted(hand_corr - doc_corr):
        diffs.append(f"Correction saisie absente de doc/ : train {c[0]} à {c[1]}, imprimé {c[2]} → {c[3]}")
    rep.banlieue_sud = diffs
    if diffs:
        rep.notes.append(f"Banlieue sud (lecture seule) : {len(diffs)} différence(s) entre la saisie et doc/ "
                         f"({n_trains} trains, {n_cells} passages comparés) — voir « banlieue_sud »")
    else:
        rep.notes.append(f"Banlieue sud (lecture seule) : grille saisie identique à doc/ ({n_trains} trains, "
                         f"{n_cells} passages, codes de jours et corrections)")
