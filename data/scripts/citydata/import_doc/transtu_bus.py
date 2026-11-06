"""Bus Transtu du Grand Tunis, depuis doc/bus/grand-tunis-transtu/donnees/ (specs/04e-import-doc.md).

Sources (toutes dans doc/) :
- `lignes.csv` et `horaires-hiver-2026-2027.csv` : lignes de l'affiche officielle hiver 2026-2027 (pôle, terminus FR/AR,
  premiers et derniers départs de chaque sens, fréquence de pointe), concordance avec l'open data, statut [C]/[I]/[A] ;
- `arrets-par-ligne.csv` : arrêts ordonnés par ligne et par sens, avec coordonnées (open data Transtu corrigé) ;
- `poles.csv` : les 16 pôles de départ ;
- positions géographiques des stations (open data brut, `sources-open-data/raw/…`) : noms arabes des arrêts ;
- `departs-opendata-depot-ben-arous.csv` : lignes sans aucun départ le dimanche (open data, hiver 2025-2026 probable).

Règles :
- une ligne de l'affiche est publiée (active) si son itinéraire open data concorde (« oui »), qu'elle est confirmée
  [C], que ses quatre horaires et sa fréquence sont publiés et que le sens de ses itinéraires est établi ; sinon elle
  est importée en brouillon (draft) si un itinéraire existe, sinon écartée (rapport `rejected`) ;
- arrêts : un lieu par arrêt physique (mêmes coordonnées, ou même nom normalisé à moins de MERGE_M) ; les deux côtés de
  la rue (ALLER / RETOUR dans la source) restent deux lieux ; un arrêt à la position manifestement fausse (homonyme
  mal géolocalisé, détour de plusieurs kilomètres) est retiré du parcours ; les arrêts des 16 pôles sont des
  « stations » (le module des pôles d'échange les reconnaît ainsi) ;
- horaires « fréquence » : pointe = fréquence officielle ; heures creuses et dimanche estimés (constantes
  EVENING_FACTOR et SUNDAY_*, tirées des départs détaillés de l'open data du dépôt de Ben Arous) ;
- durées : distance à vol d'oiseau × détour, à vitesse moyenne, + temps d'arrêt (profils FLUIDE et CHARGE).
"""

import csv
import io
import math
import re
from collections import Counter, defaultdict

from citydata.import_doc.common import (
    clean_ar, dist_m, doc_path, hhmm, i18n, minutes, norm_name, prov, read_csv, remove_generated, run_minutes, slug,
    write_yaml,
)

DATA = "bus/grand-tunis-transtu/donnees"
POSITIONS_DIR = ("sources-open-data/raw/data.transport.tn/"
                 "positions-geographiques-des-stations-du-reseau-bus-de-la-transtu")
SOURCE_LABEL = f"{DATA}/lignes.csv, horaires-hiver-2026-2027.csv, arrets-par-ligne.csv et poles.csv"
AFFICHE = "affiche Transtu « marche horaire hiver 2026-2027 » (transtu.tn, page 0143"
OPEN_DATA = ("open data Transtu (catalogue-data.transport.tn), jeux « itinéraires des lignes du réseau bus » et "
             "« positions géographiques des stations » publiés le 2026-01-25 ; réseau décrit antérieur à septembre "
             "2023 pour l'essentiel, date de relevé non publiée (doc/bus/grand-tunis-transtu/donnees-ouvertes.md)")
STOP_REF = ("Open data Transtu (catalogue-data.transport.tn, publié le 2026-01-25) : itinéraires des lignes de bus et "
            "positions des arrêts, relevés antérieurs à 2023 pour l'essentiel (date non publiée)")
OPEN_DATA_DATE = "2026-01-25"      # publication par la Transtu : dernière vérification officielle connue
AFFICHE_DATE = "2026-10-14"        # transcription de l'affiche relue image par image

COLOR, TEXT_COLOR = "#C62828", "#FFFFFF"       # couleur du mode bus (modes.yaml) : contraste 5,6:1

MERGE_M = 40            # même nom normalisé à moins de 40 m : même arrêt physique
POLE_STOP_M = 50        # arrêt du pôle : arrêt open data à moins de 50 m du point de poles.csv
POLE_M = 500            # premier arrêt open data accepté à 500 m du pôle (10 Décembre : arrêt à 308 m du point du pôle)
TERMINUS_GAP_M = 1500   # au-delà, fin de l'aller et début du retour ne sont pas au même terminus (signalé)
OUTLIER_LEG_M, OUTLIER_RATIO = 2500, 3   # arrêt à > 2,5 km de ses deux voisins et détour > 3 × leur écart

# Durées : distance × DETOUR à la vitesse de roulage, + temps d'arrêt à chaque arrêt.
DETOUR = 1.25
PROFILES = {"FLUIDE": (24, 0.4), "CHARGE": (17, 0.6)}

# Heures creuses et dimanche : analyse des 2 271 départs détaillés de l'open data du dépôt de Ben Arous (52 lignes,
# hiver 2025-2026 probable) — médiane des écarts entre départs consécutifs par tranche, rapportée à la pointe :
# - journée (09-16 h) et avant 6 h : même intervalle qu'en pointe (rapport médian 1,0 sur 93 et 32 sens de ligne) ;
# - soirée (après 19 h) : rapport médian 1,26 (27 sens de ligne) → EVENING_FACTOR ;
# - dimanche : 32 sens de ligne sur 96 sans aucun départ ; ailleurs 1,32 fois moins de départs qu'en semaine
#   (médiane, 64 sens), premier départ 30 min plus tard (médiane), dernier inchangé → SUNDAY_FACTOR, SUNDAY_DELAY_MIN.
EVENING_FACTOR = 1.25
SUNDAY_FACTOR = 1.3
SUNDAY_DELAY_MIN = 30
RULE = ("heures creuses et dimanche estimés : intervalle de pointe officiel de 0 h à 19 h, ×1,25 après 19 h ; "
        "dimanche ×1,3 toute la journée, premier départ 30 min plus tard (rapports médians des départs détaillés de "
        "l'open data du dépôt de Ben Arous, hiver 2025-2026 probable)")
# Le jeu des départs écrit « 19B » la ligne que les itinéraires et l'affiche notent 19A / 19أ (donnees-ouvertes.md §2).
DEPARTS_ALIASES = {"19B": "19A"}

AIRPORT = "المطار"
AIRPORT_STOP = "AÉROPORT TUNIS CARTHAGE"     # nom dans les positions géographiques open data
AIRPORT_ID = "BUS-AEROPORT-TUNIS-CARTHAGE"
TUNIS_MARINE = "BUS-TUNIS-MARINE"            # identifiant imposé (places/hubs.yaml)

STOPWORDS = {"cite", "el", "de", "du", "la", "le", "des", "et", "par", "terminus", "station", "rabattement", "l"}


# --- Noms ---------------------------------------------------------------------------------------------------------------

SIDE_RE = re.compile(r"[\s\-+]*\(?\s*\b(ALLER|RETOUR)\b\s*\)?\s*$", re.I)
SECTION_RE = re.compile(r"[\s\-]*\(\s*SECTION\s*\)|[\s\-]+SECTION\s*$|^\s*SECTION\s+", re.I)
TERMINUS_RE = re.compile(r"\b(TERMINUS|TEMINUS|TERMENUS\w*)\b", re.I)
# Numéros de ligne dans un nom d'arrêt : « ( L 36 B ) », « L(26A-B-82) », « L23 », « L 78 + 38 B », « 23D-23/ »,
# « (16C 58) », « 75 26A 37 » en fin de nom… (jamais un nombre seul : « Cité Ksar Saïd 2 », « Poste police (17) »).
_NL = r"(?![A-Za-zÀ-ÿ])"
LINE_REF_RES = [
    re.compile(r"\(\s*L\s*:?[^)]*\)+"),
    re.compile(r"\bL\s*\([^)]*\)"),
    re.compile(rf"\bL\s?\d+(?:\s?[A-Z]{_NL})?(?:\s*[+/\-]\s*\d*(?:\s?[A-Z]{_NL})?)*/?(?:\([A-Z\-/+ ]*\))?"),
    re.compile(r"\s*\((?=[^)]*\d[A-Z])\s*\d+[A-Z]?/?(?:[\s,\-+/]+\d+[A-Z]?/?)*\s*\)"),
    re.compile(rf"(?:[\s\-]+\d+[A-Z]?/?)*[\s\-]+\d+(?:[A-Z]{_NL}/?|/)(?:[\s,\-+/]+\d+(?:[A-Z]{_NL})?/?)*\s*$"),
]
SIDE_AR_RE = re.compile(r"[\s\-]*(ذهاب|إياب|اياب)\s*$")
_AR_L = "أبتثجحخطقصدسفا"
_AR_CODE = rf"(?:\d+\s?[{_AR_L}]?|[{_AR_L}])(?![ء-ي])"
# « خط 23ت/ث », « نهاية خط ( 43ب + 43 ) », « خطوط :32 +65 +515 ب » (خط = ligne, نهاية الخط = terminus)
KHAT_RE = re.compile(rf"(\(?\s*)(نهاية\s+)?(?:ال)?خط(?:وط)?\s*:?\s*\(?\s*{_AR_CODE}"
                     rf"(?:(?:\s*[/+\-،]\s*|\s+){_AR_CODE})*\s*/?\s*\)?")
AR_NUM_CODE_RE = re.compile(rf"(?<!\d)(\d+)(?:\s?[{_AR_L}](?![ء-ي]))?/?(?=\W|$|[ء-ي])")
ACCENTS = {
    "CITE": "Cité", "LYCEE": "Lycée", "ECOLE": "École", "MOSQUEE": "Mosquée", "MOSQUE": "Mosquée", "MARCHE": "Marché",
    "HOPITAL": "Hôpital", "DEPOT": "Dépôt", "ARRET": "Arrêt", "ENTREE": "Entrée", "CAFE": "Café",
    "COLLEGE": "Collège", "THEATRE": "Théâtre", "MINISTERE": "Ministère", "ROUTIERE": "Routière",
    "PEPINIERE": "Pépinière", "CARRIERE": "Carrière", "SOCIETE": "Société", "UNIVERSITE": "Université",
    "FACULTE": "Faculté", "CIMETIERE": "Cimetière", "MUNICIPALITE": "Municipalité", "PREFECTURE": "Préfecture",
    "RADES": "Radès", "GENERAL": "Général", "SUPERIEUR": "Supérieur", "SECURITE": "Sécurité",
    "DELEGATION": "Délégation", "EGLISE": "Église", "HOTEL": "Hôtel", "INTERIEUR": "Intérieur",
    "CENTRALE": "Centrale", "ETATS": "États", "AOUT": "Août", "DECEMBRE": "Décembre", "FEVRIER": "Février",
}
MONTHS = {"janv": "JANVIER", "févr": "FÉVRIER", "fevr": "FÉVRIER", "avr": "AVRIL", "juil": "JUILLET",
          "sept": "SEPTEMBRE", "oct": "OCTOBRE", "nov": "NOVEMBRE", "déc": "DÉCEMBRE", "dec": "DÉCEMBRE"}
SMALL_WORDS = {"de", "du", "des", "la", "le", "les", "et", "au", "aux", "en", "sur", "par", "vers"}
ACRONYMS = {"ONAS", "STEG", "ONCV", "INPFCA", "SONEDE", "CTGB", "ISET", "IHEC", "ENIT", "INSAT", "UGTT", "OACA",
            "CHU", "BNA", "UIB", "ATB", "BIAT", "SNCFT", "TGM", "RFR", "SNIT", "SIEFCOL", "STIA", "SOTUVER", "TPR",
            "ENSIT", "INAT", "ISG", "CNRPS", "IPSI", "STB", "BTS", "SOTETEL", "SIAPE", "ZI", "SNT", "UBCI",
            "CFPA", "CREPS", "ENA", "ESSECT", "FSEG", "ISSHT", "ISEAH", "SOCOMENA", "SONED", "CNSS", "CTTM", "OTC",
            "SNTRI", "SNDP"}


def _word_case(word, first):
    if re.fullmatch(r"\d+(?:EME|ÉME|ÈME|ER|ERE|ÈRE)", word, re.I):     # « 2ÉME » → « 2ème »
        return re.sub(r"[ÉE]ME$", "ème", re.sub(r"[ÈE]RE$", "ère", word.upper())).replace("ER", "er")
    if word[:1].isdigit():                                              # « 16A », « 4X4 » : codes gardés tels quels
        return word.upper()
    letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", word)
    bare = norm_name(word).upper().replace(" ", "")
    if bare in ACRONYMS or (letters and len(letters) <= 5 and not re.search(r"[AEIOUYÀ-ÿ]", letters.upper())):
        return word.upper()
    if bare in ACCENTS and re.fullmatch(r"[A-ZÀ-Ý]+", word):
        return ACCENTS[bare]
    low = word.lower()
    low = re.sub(r"ére\b", "ère", low)
    low = re.sub(r"ége\b", "ège", low)
    low = re.sub(r"(?<=\d)éme\b", "ème", low)
    if not first and low in SMALL_WORDS:
        return low
    return low[:1].upper() + low[1:]


def title_fr(text):
    """« AV DE L'ENVIRONNEMENT » → « Av de l'Environnement » ; sigles et mots sans voyelle gardés en capitales."""
    text = re.sub(r"\bDÉ(?=ENFANT)", "D'", text.strip())            # apostrophe corrompue dans la source
    tokens = re.split(r"([\s\-/()'’.&]+)", text)
    out, first = [], True
    for i, tok in enumerate(tokens):
        if not tok or re.fullmatch(r"[\s\-/()'’.&]+", tok):
            out.append(tok)
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if tok.upper() in ("D", "L") and nxt[:1] in ("'", "’"):
            out.append(tok.upper() if first else tok.lower())
        else:
            out.append(_word_case(tok, first))
        first = False
    return re.sub(r"\s+", " ", "".join(out)).strip()


def name_parts(source):
    """Nom open data → (nom sans côté de rue, ni « section », ni numéros de ligne ; côté ALLER/RETOUR ; nombres des
    numéros de ligne ôtés, ou None si rien n'a été ôté).

    Les numéros de ligne ne sont ôtés que s'il reste un vrai nom (« TERMINUS 32D » reste tel quel).
    """
    m = SIDE_RE.search(source)
    base, side = (source[:m.start()], m.group(1).upper()) if m else (source, "")
    base = SECTION_RE.sub("", base).strip(" -")
    base = re.sub(r"^(\d{1,2})-([A-Za-zéû]+)\.?$",                     # « 14-janv » : date abîmée par un tableur
                  lambda m: f"{m.group(1)} {MONTHS.get(m.group(2).lower(), m.group(2))}", base)
    stripped, removed = base, []
    for rx in LINE_REF_RES:
        removed += rx.findall(stripped)
        stripped = rx.sub(" ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip(" -,+/")
    refs = None
    if stripped != base and TERMINUS_RE.sub("", stripped).strip(" -,+/()"):
        base, refs = stripped, set(re.findall(r"\d+", " ".join(removed)))
    base = re.sub(r"(?<=\S)\(", " (", re.sub(r"\(\s*", "(", re.sub(r"\s*\)", ")", base)))
    return re.sub(r"\s+", " ", base).strip(" -"), side, refs


def ar_name(text, refs):
    """Nom arabe affiché : sans côté de rue (ذهاب / إياب), ni « قسم » (section), ni numéros de ligne quand le nom
    français en a été débarrassé (`refs`) ; parenthèses mal placées (texte retourné dans la source) retirées."""
    text = SIDE_AR_RE.sub("", clean_ar(text)).strip(" -")
    text = re.sub(r"[\s\-]*\(?\s*قسم\s*\)?", " ", text).strip(" -")
    if refs is not None:
        stripped = KHAT_RE.sub(lambda m: " نهاية الخط " if m.group(2) else " ", text)
        stripped = AR_NUM_CODE_RE.sub(lambda m: " " if m.group(1) in refs else m.group(0), stripped)
        stripped = re.sub(r"\(\s*\)", " ", stripped)
        stripped = re.sub(r"\s*[/+\-]\s*(?=\s|$)", " ", stripped)
        stripped = re.sub(r"\s+", " ", stripped).strip(" -/+،")
        if re.sub(r"(نهاية|الخط|خط|محطة)", "", stripped).strip(" -()،"):
            text = stripped
    if text.count("(") != text.count(")") or text[:1] in "()" or 0 <= text.find(")") < text.find("("):
        text = text.replace("(", " ").replace(")", " ")
    return re.sub(r"\s+", " ", text).strip(" -")


def _tokens(text):
    return {w for w in norm_name(re.sub(r"\(.*?\)", " ", text or "")).split() if w not in STOPWORDS}


def _code_slug(code):
    """« 23F/ » → « 23F-BARRE » ; « 52A+B » → « 52A-PLUS-B » (identifiant de ligne et nom de fichier)."""
    return slug(code.replace("/", "-BARRE-").replace("+", "-PLUS-"))


def _pole_short(pole):
    return re.sub(r"\s*\(.*\)\s*$", "", pole).strip()


# --- Lecture ------------------------------------------------------------------------------------------------------------

def _positions(doc):
    """Positions géographiques open data (UTF-16, tabulations, virgule décimale) : [(lat, lon, nom FR, nom AR)]."""
    path = sorted(doc_path(doc, POSITIONS_DIR).glob("stations_bus_*.csv"))[0]
    rows = []
    for r in csv.DictReader(io.StringIO(path.read_bytes().decode("utf-16")), delimiter="\t"):
        try:
            lat, lon = float(r["Latitude"].replace(",", ".")), float(r["Longitude"].replace(",", "."))
        except (KeyError, ValueError, AttributeError):
            continue
        rows.append((lat, lon, (r.get("Label_fr") or "").strip(), clean_ar(r.get("Label_ar") or "")))
    return rows


def _key(lat, lon):
    return round(float(lat), 6), round(float(lon), 6)


def _routes(rows):
    """Itinéraires open data : code → {sens: [arrêt, …]} dans l'ordre ; numéro de l'affiche → code open data."""
    routes = defaultdict(lambda: defaultdict(list))
    affiche_code = {}
    for r in rows:
        routes[r["ligne_opendata"]][r["sens"]].append(r)
        if r["ligne_affiche"]:
            affiche_code.setdefault(r["ligne_affiche"], r["ligne_opendata"])
    for code in routes:
        for sens in routes[code]:
            routes[code][sens].sort(key=lambda r: int(r["ordre"]))
    return routes, affiche_code


# --- Horaires -----------------------------------------------------------------------------------------------------------

def _time(text):
    text = (text or "").strip()
    return None if not text or text in ("-", "–", "—") else minutes(text)


def _hours(row):
    """Premiers et derniers départs par sens (minutes ; après minuit → +24 h), fréquence, liste de ce qui manque."""
    f_a, l_a = _time(row["premier_depart_pole"]), _time(row["dernier_depart_pole"])
    f_r, l_r = _time(row["premier_depart_terminus"]), _time(row["dernier_depart_terminus"])
    freq = (row["frequence_pointe_min"] or "").strip()
    missing = [label for label, v in (("premier départ du pôle", f_a), ("dernier départ du pôle", l_a),
                                      ("premier départ du terminus", f_r), ("dernier départ du terminus", l_r))
               if v is None]
    headway = int(freq) if freq.isdigit() else None
    if headway is None:
        missing.append("fréquence de pointe")
    hours = {}
    for d, first, last in (("ALLER", f_a, l_a), ("RETOUR", f_r, l_r)):
        if first is None or last is None:
            continue
        if last < first and last < 4 * 60:
            last += 24 * 60
        if last < first:
            missing.append(f"horaires du sens {d} incohérents ({hhmm(first)} → {hhmm(last)})")
            continue
        hours[d] = (first, last)
    return hours, headway, missing


def _ceil5(x):
    return int(math.ceil(x / 5 - 1e-9) * 5)


def _regimes(hours, headway, sunday_service=True):
    """Régime NORMAL ouvrable + samedi (pointe officielle, reste estimé) et régime dimanche (estimé)."""
    def envelope(by_dir):
        return {"first": hhmm(min(f for f, _ in by_dir.values())), "last": hhmm(max(l for _, l in by_dir.values())),
                "by_direction": {d: {"first": hhmm(f), "last": hhmm(l)} for d, (f, l) in by_dir.items()}}

    sunday_hours = {d: (min(f + SUNDAY_DELAY_MIN, l), l) for d, (f, l) in hours.items()}
    regimes = [
        {"periods": ["NORMAL"], "day_types": ["OUVRABLE", "SAMEDI"], "service_hours": envelope(hours),
         "bands": {
             "NUIT": {"headway_min": headway, "run_time": "FLUIDE"},
             "POINTE_MATIN": {"headway_min": headway, "run_time": "CHARGE"},
             "JOURNEE": {"headway_min": headway, "run_time": "FLUIDE"},
             "POINTE_SOIR": {"headway_min": headway, "run_time": "CHARGE"},
             "SOIREE": {"headway_min": _ceil5(headway * EVENING_FACTOR), "run_time": "FLUIDE"},
         }},
        {"periods": ["NORMAL"], "day_types": ["DIMANCHE"], "service_hours": envelope(sunday_hours),
         "bands": {"TOUTE_LA_JOURNEE": {"headway_min": _ceil5(headway * SUNDAY_FACTOR), "run_time": "FLUIDE"}}},
    ]
    return regimes if sunday_service else regimes[:1]


def _no_sunday(departs):
    """Codes latins des lignes sans aucun départ le dimanche dans l'open data du dépôt de Ben Arous."""
    weekday, sunday = Counter(), Counter()
    for r in departs:
        code = DEPARTS_ALIASES.get(r["ligne_opendata"], r["ligne_opendata"])
        (sunday if r["jour"] == "dimanche" else weekday)[code] += int(r["nb_departs"] or 0)
    return {code for code in weekday if weekday[code] and not sunday[code]}


# --- Parcours -----------------------------------------------------------------------------------------------------------

def _pt(r):
    return float(r["lat"]), float(r["lon"])


def _drop_outliers(stops, label, rejected):
    """Retire les arrêts manifestement mal géolocalisés (homonyme placé à plusieurs kilomètres du parcours)."""
    stops = list(stops)
    while len(stops) >= 3:
        worst, worst_excess = None, 0
        for i in range(1, len(stops) - 1):
            a, s, b = _pt(stops[i - 1]), _pt(stops[i]), _pt(stops[i + 1])
            d1, d2, d0 = dist_m(a, s), dist_m(s, b), dist_m(a, b)
            if d1 > OUTLIER_LEG_M and d2 > OUTLIER_LEG_M and d1 + d2 > OUTLIER_RATIO * max(d0, 1000) \
                    and d1 + d2 - d0 > worst_excess:
                worst, worst_excess = i, d1 + d2 - d0
        if worst is None:
            return stops
        s = stops.pop(worst)
        rejected.append(f"Ligne {label} : arrêt « {s['arret']} » ({s['lat']}, {s['lon']}) retiré du parcours, position "
                        f"incohérente (détour de {worst_excess / 1000:.1f} km entre ses voisins)")
    return stops


def _near(stop, point, radius):
    return stop is not None and dist_m(_pt(stop), point) <= radius


def _orient_pole(aller, retour, pole_pt):
    """Le sens ALLER part du pôle : (aller, retour, raison si le sens est indéterminé)."""
    first = lambda s: s[0] if s else None
    last = lambda s: s[-1] if s else None
    normal = _near(first(aller), pole_pt, POLE_M) + _near(last(retour), pole_pt, POLE_M)
    swapped = _near(first(retour), pole_pt, POLE_M) + _near(last(aller), pole_pt, POLE_M)
    if normal > swapped:
        return aller, retour, None
    if swapped > normal:
        return retour, aller, None
    return aller, retour, "aucun sens de l'itinéraire open data ne part du pôle de l'affiche"


def _orient_terminus(aller, retour, row, positions):
    """« Autres lignes » (pas de pôle sur l'affiche) : le sens ALLER va vers le terminus affiché, repéré par son nom
    (dans le nom d'une extrémité, sinon par les arrêts open data qui portent ce nom)."""
    ends = (aller[0], aller[-1])
    tk = _tokens(row["terminus_fr"])
    by_name = [bool(tk) and tk <= _tokens(e["arret"]) for e in ends]
    if by_name[0] != by_name[1]:
        return (retour, aller, None) if by_name[0] else (aller, retour, None)
    ar = clean_ar(row["terminus_ar"])
    hits = [(lat, lon) for lat, lon, fr, a in positions if (tk and tk <= _tokens(fr)) or (len(ar) >= 4 and ar in a)]
    if hits:
        c = (sum(h[0] for h in hits) / len(hits), sum(h[1] for h in hits) / len(hits))
        d0, d1 = dist_m(_pt(ends[0]), c), dist_m(_pt(ends[1]), c)
        if d1 <= 1500 and d0 > 3 * d1:
            return aller, retour, None
        if d0 <= 1500 and d1 > 3 * d0:
            return retour, aller, None
    return aller, retour, ("sens indéterminé : l'affiche ne donne pas le point de départ et son terminus n'est pas "
                           "repérable dans l'itinéraire open data")


# --- Programme principal ------------------------------------------------------------------------------------------------

def run(doc, src):
    lignes = read_csv(doc_path(doc, DATA, "lignes.csv"))
    affiche = {r["ligne"]: r for r in read_csv(doc_path(doc, DATA, "horaires-hiver-2026-2027.csv"))}
    poles = read_csv(doc_path(doc, DATA, "poles.csv"))
    routes, affiche_code = _routes(read_csv(doc_path(doc, DATA, "arrets-par-ligne.csv")))
    no_sunday = _no_sunday(read_csv(doc_path(doc, DATA, "departs-opendata-depot-ben-arous.csv")))
    positions = _positions(doc)
    pole_by_name = {p["pole"]: p for p in poles}
    rejected, notes = [], []

    def opendata_code(row):
        if row["ligne"] in affiche_code:
            return affiche_code[row["ligne"]]
        want = (row["opendata_depart"], row["opendata_terminus"], row["opendata_nb_arrets_aller"])
        found = [c for c, d in sorted(routes.items()) if want[0] and d.get("aller")
                 and (d["aller"][0]["arret"], d["aller"][-1]["arret"], str(len(d["aller"]))) == want]
        return found[0] if len(found) == 1 else None

    # --- 1. Lignes de l'affiche : itinéraire open data, sens, statut ---------------------------------------------------
    specs = []
    airport_stop = next((p for p in positions if p[2] == AIRPORT_STOP), None)
    for row in lignes:
        num, latin = row["ligne"], row["ligne_latin"]
        if not num:
            rejected.append(f"Ligne open data {latin} : absente de l'affiche hiver 2026-2027 (ligne supprimée, "
                            f"renumérotée ou non affichée)")
            continue
        label = f"{num} ({latin})" if latin else num
        hours, headway, missing = _hours(row)
        code = opendata_code(row)
        if code is None:
            if num == AIRPORT and airport_stop:
                # Publiée : ligne directe Tunis Marine ↔ aéroport (horaires officiels, tarif presse) ; les deux arrêts
                # brefs intermédiaires, sans position connue, ne servent pas aux voyageurs de l'aéroport.
                specs.append({"row": row, "airport": airport_stop, "hours": hours, "headway": headway, "reasons": [],
                              "info": [
                    "parcours : les deux terminus seulement (arrêts brefs à l'Office de l'aviation civile et à la gare "
                    "de fret, Webdo 2026-03-13, sans position)",
                    "aucun numéro sur l'affiche (« 35 » selon Webdo, non confirmé)"]})
                continue
            rejected.append(f"Ligne {label} : aucun itinéraire dans l'open data (ligne créée ou modifiée après le "
                            f"relevé) — {row['note'] or row['terminus_fr']}")
            continue
        reasons = []
        aller = _drop_outliers(routes[code].get("aller", []), f"{label} aller", rejected)
        retour = _drop_outliers(routes[code].get("retour", []), f"{label} retour", rejected)
        if not aller:
            aller, retour = retour, []
        if len(aller) < 2:
            rejected.append(f"Ligne {label} : itinéraire open data inutilisable (moins de deux arrêts)")
            continue
        if row["pole"] in pole_by_name:
            p = pole_by_name[row["pole"]]
            aller, retour, why = _orient_pole(aller, retour, (float(p["lat"]), float(p["lon"])))
        else:
            aller, retour, why = _orient_terminus(aller, retour, row, positions)
        if why:
            reasons.append(why)
        if row["concordance_opendata"] != "oui":
            detail = row["note"].split("|")[-1].strip() if row["note"] else ""
            reasons.append(f"itinéraire open data « {row['concordance_opendata']} »{' (' + detail + ')' if detail else ''}")
        if row["statut"] != "[C]":
            reasons.append(f"statut {row['statut']} : {(row['note'] or 'non confirmée').split('|')[0].strip()}")
        if retour and dist_m(_pt(aller[0]), _pt(retour[0])) < 200 and dist_m(_pt(aller[-1]), _pt(retour[-1])) < 200:
            reasons.append("sens retour de l'open data identique à l'aller (mêmes extrémités)")
            retour = []
        if missing:
            reasons.append("horaires incomplets sur l'affiche (manque : " + ", ".join(missing) + ")")
        if retour and dist_m(_pt(aller[-1]), _pt(retour[0])) > TERMINUS_GAP_M:
            notes.append(f"Ligne {label} : fin de l'aller et début du retour à "
                         f"{dist_m(_pt(aller[-1]), _pt(retour[0])) / 1000:.1f} km (itinéraire open data tel quel)")
        specs.append({"row": row, "code": code, "aller": aller, "retour": retour if len(retour) >= 2 else [],
                      "hours": hours, "headway": headway, "reasons": reasons})

    # --- 2. Arrêts physiques : dédoublonnage ---------------------------------------------------------------------------
    def raw_key(r):
        return (r["arret"],) + _key(r["lat"], r["lon"])

    uses = Counter(raw_key(r) for spec in specs for r in spec.get("aller", []) + spec.get("retour", []))
    keys = sorted(uses)
    parent = {k: k for k in keys}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_coord, by_norm = defaultdict(list), defaultdict(list)
    for k in keys:
        core, side, _ = name_parts(k[0])
        by_coord[k[1:]].append(k)
        by_norm[(norm_name(core), side)].append(k)
    for group in by_coord.values():                 # mêmes coordonnées : même point (variantes d'orthographe)
        for k in group[1:]:
            union(group[0], k)
    for group in by_norm.values():                  # même nom normalisé (côté de rue compris) à moins de MERGE_M
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if dist_m(a[1:], b[1:]) < MERGE_M:
                    union(a, b)
    clusters = defaultdict(list)
    for k in keys:
        clusters[find(k)].append(k)

    pos_by_key = defaultdict(list)
    for p in positions:
        pos_by_key[_key(p[0], p[1])].append(p)

    def arabic(name, lat, lon):
        """Nom arabe des positions open data : mêmes coordonnées, sinon le plus proche à 3 m, sinon même nom à 150 m."""
        cands = [p for p in pos_by_key.get((lat, lon), []) if p[3]]
        if not cands:
            near = sorted((dist_m((lat, lon), p[:2]), p) for p in positions
                          if p[3] and abs(p[0] - lat) < 0.002 and abs(p[1] - lon) < 0.002)
            cands = [p for d, p in near if d <= 3] or [p for d, p in near
                                                       if d <= 150 and norm_name(p[2]) == norm_name(name)][:1]
        same = [p for p in cands if norm_name(p[2]) == norm_name(name)] or cands
        return max((p[3] for p in same), key=lambda a: (len(a), a), default=None)

    # Arrêt de chaque pôle : arrêt open data à moins de POLE_STOP_M du point de poles.csv.
    pole_of = {}
    for p in poles:
        pt = (float(p["lat"]), float(p["lon"]))
        best = min(clusters, key=lambda c: (min(dist_m(k[1:], pt) for k in clusters[c]), c), default=None)
        if best is not None and min(dist_m(k[1:], pt) for k in clusters[best]) <= POLE_STOP_M:
            pole_of[best] = p

    places, place_of = {}, {}
    used_ids = {"BUS-" + slug(_pole_short(p["pole"])) for p in pole_of.values()} | {AIRPORT_ID}
    pending = []
    for root, members in sorted(clusters.items()):
        rep = max(members, key=lambda k: (sum(uses[m] for m in members if m[0] == k[0]), len(k[0]), k))
        core, side, refs = name_parts(rep[0])
        ar = next((a for a in (arabic(m[0], m[1], m[2]) for m in sorted(members, key=lambda k: (-uses[k], k))) if a),
                  "")
        place = {"kind": "stop", "name": i18n(title_fr(core), ar_name(ar, refs) if ar else ""),
                 "lat": rep[1], "lon": rep[2], "sources": sorted({m[0] for m in members})}
        if ar and not re.search(r"[؀-ۿ]", ar):
            notes.append(f"Arrêt « {rep[0]} » : nom « arabe » de l'open data en lettres latines (« {ar} »), gardé tel quel")
        if root in pole_of:
            p = pole_of[root]
            place.update({"id": "BUS-" + slug(_pole_short(p["pole"])), "kind": "station", "pole": p,
                          "name": i18n(_pole_short(p["pole"]), p["pole_ar"]),
                          "aliases": [title_fr(name_parts(s)[0]) for s in place["sources"]]})
            places[place["id"]] = place
        else:
            place["base"] = "BUS-" + slug(f"{core} {side}")
            pending.append(place)
        for m in members:
            place_of[m] = place
    # Identifiants : nom (et côté de rue) ; homonymes numérotés -2, -3… du nord au sud.
    by_base = defaultdict(list)
    for place in pending:
        by_base[place["base"]].append(place)
    for base, group in sorted(by_base.items()):
        n = 1
        for place in sorted(group, key=lambda p: (-p["lat"], p["lon"])):
            pid = base
            while pid in used_ids:
                n += 1
                pid = f"{base}-{n}"
            used_ids.add(pid)
            place["id"] = pid
            places[pid] = place

    # --- 3. Lignes -------------------------------------------------------------------------------------------------
    lines_out = []
    for spec in specs:
        row = spec["row"]
        num, latin = row["ligne"], row["ligne_latin"]
        is_airport = "airport" in spec
        if is_airport:
            if TUNIS_MARINE not in places:
                rejected.append("Ligne de l'aéroport : arrêt du pôle Tunis Marine introuvable")
                continue
            lat, lon, fr, _ = spec["airport"]
            apt = {"id": AIRPORT_ID, "kind": "stop",
                   "name": i18n(row["terminus_fr"], row["terminus_ar"]), "lat": round(lat, 6), "lon": round(lon, 6),
                   "sources": [fr], "airport": True}
            places[apt["id"]] = apt
            seqs = {"ALLER": [places[TUNIS_MARINE], apt], "RETOUR": [apt, places[TUNIS_MARINE]]}
        else:
            seqs = {}
            for d, stops in (("ALLER", spec["aller"]), ("RETOUR", spec["retour"])):
                seq = []
                for r in stops:
                    pl = place_of[raw_key(r)]
                    if not seq or seq[-1]["id"] != pl["id"]:
                        seq.append(pl)
                if len(seq) >= 2:
                    seqs[d] = seq
            if "ALLER" not in seqs:
                rejected.append(f"Ligne {num} ({latin}) : moins de deux arrêts distincts dans l'itinéraire open data")
                continue
        missing_ar = sorted({pl["id"] for seq in seqs.values() for pl in seq if not pl["name"].get("ar")})
        if missing_ar and not spec["reasons"]:
            spec["reasons"].append("arrêt(s) sans nom arabe dans l'open data : " + ", ".join(missing_ar))
        status = "draft" if spec["reasons"] else "active"

        patterns = []
        for d, seq in seqs.items():
            pts = [(pl["lat"], pl["lon"]) for pl in seq]
            patterns.append({"id": d, "direction": d, "main": True, "stops": [pl["id"] for pl in seq],
                             "run_times": {prof: run_minutes(pts, speed, dwell, DETOUR)
                                           for prof, (speed, dwell) in PROFILES.items()}})
        pole = pole_by_name.get(row["pole"])
        if pole:
            origin = i18n(_pole_short(pole["pole"]), pole["pole_ar"])
        else:
            origin = dict(seqs["ALLER"][0]["name"])
        directions = [{"id": "ALLER", "headsign": i18n(row["terminus_fr"], row["terminus_ar"])}]
        if "RETOUR" in seqs:
            directions.append({"id": "RETOUR", "headsign": {k: v for k, v in origin.items() if v}})
        code = "Aéroport" if is_airport else latin
        line = {
            "id": "TRANSTU-BUS-" + ("AEROPORT" if is_airport else _code_slug(latin)),
            "network": "TRANSTU", "mode": "BUS", "public_code": code,
            "name": i18n("Bus de l'aéroport", "حافلة المطار") if is_airport else i18n(f"Bus {latin}", f"حافلة {num}"),
            "long_name": {k: v for k, v in i18n(f"{origin['fr']} – {row['terminus_fr']}",
                                                f"{origin.get('ar') or ''} – {clean_ar(row['terminus_ar'])}").items()},
            "color": COLOR, "text_color": TEXT_COLOR, "status": status,
            "directions": directions, "patterns": patterns,
        }
        hours, headway = spec["hours"], spec["headway"]
        schedule = {"kind": "frequency", "regimes": []}
        dir_ids = [d["id"] for d in directions]
        if headway and all(d in hours for d in dir_ids):
            schedule["regimes"] = _regimes({d: hours[d] for d in dir_ids}, headway, latin not in no_sunday)
            if latin in no_sunday:
                schedule["no_service"] = [{"periods": ["NORMAL", "ETE", "RAMADAN"], "day_types": ["DIMANCHE"]}]
        line["schedule"] = schedule
        line["fare"] = "FARE-TRANSTU-BUS-AEROPORT" if is_airport else "FARE-TRANSTU-BUS"

        image = (affiche.get(num) or {}).get("image_source") or row["source"]
        parts = [
            f"Premiers et derniers départs (pôle {row['premier_depart_pole'] or '–'} → {row['dernier_depart_pole'] or '–'}, "
            f"terminus {row['premier_depart_terminus'] or '–'} → {row['dernier_depart_terminus'] or '–'}) et fréquence de "
            f"pointe ({row['frequence_pointe_min'] or '–'} min) : {AFFICHE}, {image}) [officiel]",
            (f"arrêts : {OPEN_DATA}, ligne open data « {spec['code']} »" if not is_airport else
             "arrêts : Tunis Marine (itinéraires open data) et aéroport (positions géographiques open data, "
             "« AÉROPORT TUNIS CARTHAGE ») ; arrêts et tarif : Webdo, 2026-03-13"),
            RULE,
            "dimanche : aucun départ dans l'open data du dépôt de Ben Arous" if "no_service" in schedule else "",
            f"durées estimées depuis les distances (détour ×{DETOUR} ; {PROFILES['FLUIDE'][0]} km/h et "
            f"{PROFILES['FLUIDE'][1]} min par arrêt en trafic fluide, {PROFILES['CHARGE'][0]} km/h et "
            f"{PROFILES['CHARGE'][1]} min en trafic chargé)",
        ]
        parts.extend(spec.get("info", []))
        if spec["reasons"]:
            parts.insert(0, "BROUILLON : " + " ; ".join(spec["reasons"]))
        line["provenance"] = prov("ESTIMATION", " ; ".join(p for p in parts if p), AFFICHE_DATE)
        filename = "bus-aeroport.yaml" if is_airport else f"bus-{_code_slug(latin).lower()}.yaml"
        lines_out.append((filename, line, spec))

    # --- 4. Lieux : statut d'après les lignes qui les desservent --------------------------------------------------------
    served = defaultdict(set)
    for _, line, _ in lines_out:
        for pat in line["patterns"]:
            for sid in pat["stops"]:
                served[sid].add(line["status"])
    out_places = []
    for pid in sorted(served):
        pl = places[pid]
        entry = {"id": pid, "kind": pl["kind"], "name": {k: v for k, v in pl["name"].items() if v}}
        aliases = sorted({a for a in pl.get("aliases", []) if a != entry["name"]["fr"]})
        if aliases:
            entry["aliases"] = aliases
        entry.update({"lat": pl["lat"], "lon": pl["lon"], "status": "active" if "active" in served[pid] else "draft"})
        if pl.get("pole"):
            p = pl["pole"]
            doubt = f" ; rapprochement incertain [I] : {p['source_coordonnees']}" if "[I]" in p["source_coordonnees"] else ""
            ref = (f"{STOP_REF} ; arrêt « {' » / « '.join(pl['sources'])} », pôle « {p['pole']} » de l'affiche hiver "
                   f"2026-2027 (doc/bus/grand-tunis-transtu/donnees/poles.csv){doubt}")
        elif pl.get("airport"):
            ref = (f"{STOP_REF} ; arrêt « {pl['sources'][0]} » ; nom de l'affiche hiver 2026-2027 ; arrêt face à la "
                   f"station de taxis, porte des arrivées (Webdo, 2026-03-13)")
        else:
            ref = f"{STOP_REF} ; arrêt « {' » / « '.join(pl['sources'])} »"
        entry["provenance"] = prov("OFFICIEL", ref, OPEN_DATA_DATE)
        out_places.append(entry)

    # --- 5. Écriture -------------------------------------------------------------------------------------------------
    lines_dir = src / "networks" / "transtu" / "lines"
    fares_dir = src / "networks" / "transtu" / "fares"
    places_path = src / "places" / "grand-tunis" / "bus-transtu.yaml"
    written = [write_yaml(places_path, out_places, f"{DATA}/arrets-par-ligne.csv et {POSITIONS_DIR}")]
    keep = set()
    for filename, line, spec in sorted(lines_out, key=lambda x: x[0]):
        written.append(write_yaml(lines_dir / filename, line, SOURCE_LABEL))
        keep.add(filename)
        if spec["reasons"]:
            rejected.append(f"Ligne {spec['row']['ligne']} ({line['public_code']}) importée en brouillon : "
                            + " ; ".join(spec["reasons"]))
    fares = set()
    if any(line["fare"] == "FARE-TRANSTU-BUS-AEROPORT" for _, line, _ in lines_out):
        written.append(write_yaml(fares_dir / "fare-transtu-bus-aeroport.yaml", {
            "id": "FARE-TRANSTU-BUS-AEROPORT", "model": "flat", "currency": "TND", "categories": ["PLEIN"],
            "versions": [{"valid_from": "2026-03-13", "price_millimes": {"PLEIN": 1000}}],
            # Prix rapporté par la presse (statut [C] dans doc/), pas publié par la Transtu : SIGNALEMENT.
            "provenance": prov("SIGNALEMENT", "Ligne Tunis Marine – aéroport Tunis-Carthage : ticket à 1,000 DT selon "
                                              "la presse (Webdo, 2026-03-13 ; confirmé [C] dans doc/bus/grand-tunis-"
                                              "transtu/services-speciaux.md §1), non publié sur transtu.tn ; date "
                                              "d'entrée en vigueur inconnue (date de l'article)", AFFICHE_DATE),
        }, "bus/grand-tunis-transtu/services-speciaux.md"))
        fares.add("fare-transtu-bus-aeroport.yaml")

    removed = []
    for path in sorted(lines_dir.glob("bus-*.yaml")):          # réseau de test (bus-b1), lignes disparues
        if path.name not in keep and remove_generated(path):
            removed.append(str(path))
    for path in sorted(fares_dir.glob("fare-transtu-bus-*.yaml")):
        if path.name not in fares and remove_generated(path):
            removed.append(str(path))
    for path in sorted((src / "places" / "grand-tunis").glob("bus-*.yaml")):   # arrêts du réseau de test
        if path != places_path and remove_generated(path):
            removed.append(str(path))

    # --- 6. Rapport --------------------------------------------------------------------------------------------------
    for prof in PROFILES:
        km = mn = 0.0
        for _, line, _ in lines_out:
            if line["status"] != "active":
                continue
            for pat in line["patterns"]:
                pts = [(places[s]["lat"], places[s]["lon"]) for s in pat["stops"]]
                km += sum(dist_m(a, b) for a, b in zip(pts, pts[1:])) * DETOUR / 1000
                mn += sum(pat["run_times"][prof])
        if mn:
            notes.append(f"Vitesse commerciale moyenne {prof} des lignes actives (arrêts compris, distance × {DETOUR}) : "
                         f"{km / mn * 60:.1f} km/h")
    n_pass = sum(uses.values())
    notes.append(f"Arrêts : {n_pass} passages ligne-arrêt dans les itinéraires retenus → {len(keys)} arrêts distincts "
                 f"(nom, position) → {len(clusters)} arrêts physiques (mêmes coordonnées, ou même nom normalisé et même "
                 f"côté de rue à moins de {MERGE_M} m) ; {len(out_places)} lieux écrits (arrêt de l'aéroport compris)")
    notes.append("Règle des horaires estimés : " + RULE)
    no_sun = sorted(line["public_code"] for _, line, _ in lines_out if line["schedule"].get("no_service"))
    notes.append("Sans service le dimanche (open data du dépôt de Ben Arous) : " + (", ".join(no_sun) or "—"))
    written_ids = {p["id"] for p in out_places}
    poles_out = {}
    for root, p in pole_of.items():
        pid = "BUS-" + slug(_pole_short(p["pole"]))
        if pid in written_ids:
            poles_out[p["pole"]] = pid
    for p in poles:
        if p["pole"] not in poles_out:
            notes.append(f"Pôle {p['pole']} : aucun arrêt des lignes importées à moins de {POLE_STOP_M} m de son point")
    status_count = Counter(line["status"] for _, line, _ in lines_out)
    place_count = Counter(p["status"] for p in out_places)
    counts = {"arrets": len(out_places), "arrets_actifs": place_count["active"],
              "arrets_brouillon": place_count["draft"], "arrets_avant_dedoublonnage": len(keys),
              "passages_ligne_arret": n_pass, "lignes": len(lines_out), "lignes_actives": status_count["active"],
              "lignes_brouillon": status_count["draft"], "tarifs": len(fares)}
    return {"written": [str(p) for p in written], "removed": removed, "counts": counts, "rejected": rejected,
            "notes": notes, "poles": dict(sorted(poles_out.items()))}
