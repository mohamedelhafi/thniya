"""Autocars interurbains de la SNTRI (specs/04e-import-doc.md).

Sources lues dans doc/ :
- base horaire du site officiel, consultée le 2026-10-14 : bus/regional-interurbain/donnees/sntri-lignes.csv (lignes
  actives, terminus, plein tarif) et sntri-arrets-horaires.csv (arrêts dans l'ordre, km, heures aller et retour) ;
- noms arabes des arrêts : liste « stationsNames » de la page d'accueil du site (raw/sntri.com.tn/) ;
- noms des destinations (FR et AR) : tableaux de la fiche bus/regional-interurbain/sntri.md ;
- jours sans service : jeu open data « horaires des bus de la SNTRI » (colonne reprise dans sntri-lignes.csv) ;
- coordonnées : référentiel national d'arrêts, cartographie des stations SNTRI, GTFS SNTRI 2020, stations de la SRT
  Médenine (data.transport.tn) et gares routières OpenStreetMap (raw/osm/).

Heures du site : par sens, on garde la plus longue suite d'heures croissantes d'un terminus à l'autre (coquilles
retirées) ; un sens qui perd plus d'un tiers de ses arrêts n'est pas importé.

Géocodage des libellés du site (majuscules, abrégés : « B.EL.HAFFEY », « EMB.SBEITLA ») :
1. candidats par nom (orthographe normalisée, abréviations du site, quelques équivalences listées dans ALIASES) ;
   les candidats à moins de CLUSTER_KM l'un de l'autre forment un même point ;
2. cohérence sur chaque ligne : la distance à vol d'oiseau entre deux arrêts ne dépasse ni les kilomètres parcourus
   (+15 %, +4 km), ni ce que permet l'horaire (110 km/h, +6 km), et n'est pas trop courte pour les km parcourus ;
3. propagation depuis des points sûrs (gares routières de Tunis, arrêts où le relevé terrain et la cartographie
   concordent) : un arrêt n'est placé que s'il est confirmé par un voisin déjà placé de la même ligne (borne
   ≤ CONFIRM_KM). Entre plusieurs points compatibles : le plus confirmé, puis nom exact dans une source qui ne
   recopie pas le site, puis nombre de sources indépendantes, puis source (relevé terrain, cartographie SNTRI,
   GTFS 2020, OSM, autres sociétés). Deux points à plus de TIE_KM restant à égalité : doute, l'arrêt est écarté.
   Un libellé confirmé à deux endroits distants de plus de HOMONYM_KM sur des lignes différentes désigne deux lieux
   (homonymes : « EL HAMMA » de Gabès et du Jérid) ;
4. arbitrage final des conflits : l'arrêt le plus en conflit sur une ligne, puis le moins confirmé sur le réseau, est
   retiré de cette ligne.
Une fois les lieux placés, un arrêt dont l'heure impose plus de MAX_KMH à vol d'oiseau est retiré du sens concerné.
Un arrêt sans nom arabe sourcé reste en brouillon et n'est pas desservi par les lignes actives.
"""

import csv
import io
import json
import re
import unicodedata
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from citydata.import_doc.common import (
    clean_ar, dist_m, doc_path, dt_to_millimes, hhmm, in_tunisia, minutes, norm_name, prov, read_csv,
    remove_generated, slug, write_text, write_yaml,
)

NETWORK = "SNTRI"
VERSION = "SITE-2026-10-14"
VALID_FROM = "2026-10-14"
# Le site ne publie aucune fin de validité : la grille vaut jusqu'à ce qu'elle soit périmée selon la règle du projet
# (reference/modes.yaml, BUS : horaires à revérifier après 180 jours), soit 2026-10-14 + 180 jours.
VALID_TO = "2027-04-12"
COLOR, TEXT_COLOR = "#00695C", "#FFFFFF"          # contraste 6,6:1
SITE_URL = "https://sntri.com.tn"
SITE_REF = "sntri.com.tn, base horaire de l'application web (consultée le 2026-10-14)"
PHONE = "+216 80 104 433"                         # service clients et réservation (fiche SNTRI)

THEME = ("bus", "regional-interurbain")
RAW = ("sources-open-data", "raw")
SRC_DOC = "bus/regional-interurbain/donnees/sntri-*.csv, fiche sntri.md et sources-open-data/raw (SNTRI, OSM)"

# Tolérances du contrôle géographique
KM_FACTOR, KM_MARGIN = 1.15, 4.0       # distance à vol d'oiseau ≤ km parcourus × 1,15 + 4 km
LOW_FACTOR, LOW_MARGIN = 4.5, 6.0      # … et ≥ (km parcourus − 6) / 4,5 (deux arrêts distincts ne se confondent pas)
SPEED_KMH, TIME_MARGIN = 110, 6.0      # … et ≤ durée × 110 km/h + 6 km
GROSS_KMH, SOFT_KMH = 200, 105        # heures du site : vitesse impossible / douteuse entre deux arrêts (km du site)
MAX_KMH = 110                          # après géocodage : vitesse à vol d'oiseau impossible (heures arrondies : +3 min)
CONFIRM_KM = 90.0                      # un voisin confirme un arrêt si la borne entre eux est ≤ 90 km
CLUSTER_KM = 1.5                       # candidats à moins de 1,5 km : un même point
SAME_PLACE_KM = 5.0                    # deux positions aussi bien confirmées à plus de 5 km : doute…
TIE_KM = 6.0                           # … départagé par la source jusqu'à 6 km, l'arrêt est écarté au-delà
HOMONYM_KM = 20.0                      # un même libellé peut désigner deux lieux distants de plus de 20 km (homonymes)
MERGE_M = 200                          # deux libellés placés à moins de 200 m : un seul lieu

# Gares routières de Tunis (fiche SNTRI : Bab Alioua = « TUNIS SUD », Bab Saadoun = « TUNIS NORD »).
GARES = {
    "TUNIS SUD": {
        "fr": "Gare routière Tunis Sud (Bab Alioua)", "short": "Tunis Sud",
        "aliases": ["Tunis Sud", "Bab Alioua", "Gare routière Sud", "باب عليوة"],
        "names": {"tunis sud", "beb alioua", "gare routiere b alioua", "grt sud", "grts depart", "grts arrivee",
                  "gare routiere de tunis sud bab alioua", "gare routiere de tunis sud"},
    },
    "TUNIS NORD": {
        "fr": "Gare routière Tunis Nord (Bab Saadoun)", "short": "Tunis Nord",
        "aliases": ["Tunis Nord", "Bab Saadoun", "Gare routière Nord", "باب سعدون"],
        "names": {"tunis nord", "gare routiere b saadoun", "grt nord", "gare routiere nord"},
    },
}

# Équivalences de noms que la normalisation ne trouve pas seule (ordre des mots, mot générique) ; chaque
# correspondance reste soumise au contrôle géographique.
ALIASES = {
    "B. CASERNE": ["Caserne Bouficha"],
    "BIR ALI": ["Bir Ali Ben Khelifa", "Bir Ali ben khlifa"],
    "EL HAMMA": ["El Hamma (Ejjerid)", "Hamet el jerid"],         # homonyme : El Hamma du Jérid (lignes de Tozeur)
    "ZAAFRANA": ["Zafrana douz"],                                 # homonyme : Zaafrane, près de Douz (ligne 194)
    "EMB.HAFFOUZ": ["Carrefour Haffouz"],
    "EMB.SBEITLA": ["Carrfour Sebitla"],
    "ET.TEJEROUIN": ["Et tejrouine"],
    "O. LAKSAB": ["Oued El Ksab"],
    "SIDI AHMED": ["Sidi Ahmed Jedidi", "Sidi-Ahmed Jedidi", "sidi ahmed jedid"],
    "TRIPOLI": ["GR Tripoli"],                                    # hors de Tunisie : refusé, mais signalé comme tel
}

# Abréviations du site, développées seulement si le nom arabe officiel le confirme : (début du mot arabe, forme)
EXPAND = {
    "a": [("عين", "Ain")],
    "b": [("بئر", "Bir"), ("برج", "Borj"), ("بن", "Ben"), ("براكة", "Barraket"), ("بوفيشة", "Bouficha")],
    "d": [("ذراع", "Dhraa")],
    "e": [("مفترق", "Embranchement")],
    "emb": [("مفترق", "Embranchement")],
    "emt": [("مفترق", "Embranchement")],
    "ent": [("مدخل", "Entrée")],
    "et": [("مدخل", "Entrée")],
    "f": [("فندق", "Fondouk")],
    "h": [("حجرة", "Hajret"), ("حمام", "Hammam")],
    "j": [("جبل", "Jebel")],
    "k": [("قلعة", "Kalaat")],
    "kt": [("القلعة", "Kalaa")],
    "m": [("منزل", "Menzel"), ("ماجل", "Majel")],
    "o": [("واد", "Oued")],
    "pt": [("قنطرة", "Pont")],
    "reg": [("رجيم", "Regim")],
    "s": [("سيدي", "Sidi")],
    "tejer": [("تاجروين", "Tajerouine")],
}

WEEKDAY_CODES = {"lun": ("MON", "le lundi", "يوم الاثنين"), "mar": ("TUE", "le mardi", "يوم الثلاثاء"),
                 "mer": ("WED", "le mercredi", "يوم الأربعاء"), "jeu": ("THU", "le jeudi", "يوم الخميس"),
                 "ven": ("FRI", "le vendredi", "يوم الجمعة"), "sam": ("SAT", "le samedi", "يوم السبت"),
                 "dim": ("SUN", "le dimanche", "يوم الأحد")}

OSM_EXCLUDE = ("louage", "لواج", "taxi", "تاكسي", "أجرة", "اجرة", "transtu", "transutu", "نقل تونس")
FR_GENERIC = {"gare", "routiere", "routier", "station", "bus", "de", "du", "des", "d", "grande", "grandes", "lignes",
              "longues"}
AR_GENERIC = {"محطة", "محطّة", "المحطة", "حافلات", "الحافلات", "الحافلة", "الباص", "النقل", "البري", "البرّي",
              "للنقل", "الوطنية", "الوطنيّة"}

ARABIC = re.compile(r"[\u0600-\u06FF]")
LATIN = re.compile(r"[A-Za-z]")
ARTICLES = {"el", "al", "le", "la", "les", "l", "de", "du", "des", "d", "et", "es", "ech", "ed", "en", "er", "ez",
            "ej"}


# --- Textes ------------------------------------------------------------------------------------------------------

def _ascii(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\bk\.\s*m\.", "km", text)
    return text.replace("'", "").replace("`", "")


def _tokens(text):
    """« B.EL.HAFFEY » → [("b", True), ("el", True), ("haffey", False)] ; « KM44 » → [("km", F), ("44", F)]."""
    return [(m.group(1), bool(m.group(2))) for m in re.finditer(r"([a-z]+|[0-9]+)(\.?)", _ascii(text))]


def _significant(tokens):
    return [t for t in tokens if not (t[0] in ARTICLES and (not t[1] or t[0] in ("el", "l")))]


def _word(w):
    w = w.replace("dj", "j").replace("q", "k")
    w = re.sub(r"^e([bcdfgjklmnprstvxz])\1", r"\1", w)      # article assimilé : Ennaima, Errhima, Essabria
    w = re.sub(r"(.)\1+", r"\1", w)
    return w[:-1] if len(w) > 3 and w.endswith("e") else w


def _sounds(w):
    """Graphies équivalentes des transcriptions de l'arabe : kh/k, gh/g, dh/d, th/t, ch/sh, g/k (ق noté g ou k)."""
    w = _word(w)
    for a, b in (("kh", "k"), ("gh", "g"), ("dh", "d"), ("th", "t"), ("ch", "c"), ("sh", "c"), ("ph", "f"),
                 ("g", "k")):
        w = w.replace(a, b)
    return w


def _skel(w):
    return re.sub(r"(.)\1+", r"\1", re.sub(r"[aeiouy]", "", _sounds(w)))


def _compact(text):
    return re.sub(r"[^a-z0-9]", "", _ascii(text))


SOFT = set("aeiouyh")


def _near(a, b):
    """Une seule différence, portant sur une voyelle ou un « h » (« jedid » / « jdid », « kit » / « khit »)."""
    if a == b:
        return True
    if len(a) == len(b):
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        return len(diff) == 1 and set(diff[0]) <= SOFT
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return len(long_) - len(short) == 1 and any(long_[:k] + long_[k + 1:] == short and long_[k] in SOFT
                                                 for k in range(len(long_)))


def _shape(w):
    """Consonnes, chaque groupe de voyelles réduit à « * » : « khaier » et « khiar » → « k*r »."""
    return re.sub(r"(.)\1+", r"\1", re.sub(r"[aeiouy]+", "*", _sounds(w)))


def _tok_match(a, b):
    """Un mot du libellé du site (mot, abrégé) et un mot du candidat désignent-ils la même chose ?"""
    (wa, abbr), wb = a, b
    if wa.isdigit() or wb.isdigit():
        return wa == wb
    if abbr and len(wa) <= 5 and (_word(wb).startswith(_word(wa)) or wb.startswith(wa)):
        return True
    sa, sb = _skel(wa), _skel(wb)
    if len(sa) >= 3 and sa == sb:
        return True                                    # mêmes consonnes : Sejnane / Sejnene, Dehmani / Dahmani
    if len(sa) >= 2 and _shape(wa) == _shape(wb):
        return True                                    # mêmes consonnes et mêmes groupes de voyelles : Khaier / Khiar
    na, nb = _word(wa), _word(wb)
    return na == nb or (min(len(na), len(nb)) >= 3 and _near(na, nb))


def _variants(name):
    """Formes comparables d'un nom de candidat : tel quel, et « Elguetar » → « El guetar »."""
    a = _ascii(name)
    out = [a]
    if re.match(r"^el[a-z]{3,}", a):
        out.append("el " + a[2:])
    return out


def _first(text):
    toks = _significant(_tokens(text))
    return _word(toks[0][0])[:1] if toks else ""


def _match(label, name):
    """Le nom d'un candidat désigne-t-il le libellé du site ? (orthographe et abréviations tolérées)"""
    if _compact(label) == _compact(name):
        return True
    b = [w for w, _ in _significant(_tokens(name))]
    for variant in _variants(label):              # « ELFAOUAR » se compare aussi comme « EL FAOUAR »
        a = _significant(_tokens(variant))
        if not any(w.isdigit() for w, _ in a):
            while b and b[-1].isdigit():           # « SMAR 1 », « EL MAOUNA 2 » : arrêts numérotés d'un lieu
                b.pop()
        if a and len(a) == len(b) and all(_tok_match(x, y) for x, y in zip(a, b)):
            return True
    return False


def _title(word):
    return "-".join("'".join(p[:1].upper() + p[1:].lower() for p in part.split("'")) for part in word.split("-"))


def _pretty(label, ar):
    """Libellé du site → nom affiché : abréviations développées quand le nom arabe officiel le confirme."""
    parts = re.findall(r"[A-Za-z0-9'\-]+\.?", label)
    arw = (ar or "").split()
    out = []
    for i, part in enumerate(parts):
        abbr, w = part.endswith("."), part.rstrip(".")
        key = _ascii(w)
        if abbr and key in EXPAND and i < len(arw):
            full = next((f for pre, f in EXPAND[key]
                         if arw[i] == pre or (len(pre) > 2 and arw[i].startswith(pre))), None)
            if full:
                out.append(full)
                continue
        m = re.fullmatch(r"(?i)km(\d+)", w)
        if m:
            out.append(f"Km {m.group(1)}")
            continue
        if re.fullmatch(r"(?i)el[a-z]{3,}", w) and i < len(arw) and arw[i].startswith("ال"):
            out.append("El " + _title(w[2:]))             # « ELFAOUAR » (الفوار) → « El Faouar »
            continue
        keep_dot = abbr and len(w) <= 2 and key not in ARTICLES
        out.append(_title(w) + ("." if keep_dot else ""))
    return " ".join(out)


def _short(fr):
    """« Djerba – Houmt Souk » → « Djerba (Houmt Souk) » : nom de terminus utilisable dans « A – B »."""
    for sep in (" – ", " / ", ", "):
        if sep in fr:
            head, tail = fr.split(sep, 1)
            return f"{head} ({tail})"
    return fr


def _ar_ok(fr, ar):
    """Nom arabe utilisable : en écriture arabe, et reprenant les nombres du libellé (« KM44 » → « كلم 44 »)."""
    if not ar or not ARABIC.search(ar) or LATIN.search(ar):
        return False
    digits = ar.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return all(d in digits for d in re.findall(r"\d+", fr))


def _rel(path):
    return str(path)


# --- Site SNTRI --------------------------------------------------------------------------------------------------

@dataclass
class Stop:
    idx: int
    label: str
    km: float
    go: int
    back: int


@dataclass
class SLine:
    code: str
    row: dict
    stops: list
    directions: list = field(default_factory=list)    # sens dont les heures sont exploitables (ALLER, RETOUR)


def _site_arabic(doc):
    html = doc_path(doc, *RAW, "sntri.com.tn", "sntri_home_destinations.html").read_text(encoding="utf-8")
    start = html.index("{", html.index("window.__PRELOADED_STATE__"))
    state, _ = json.JSONDecoder().raw_decode(html[start:])
    seen = defaultdict(set)
    for item in state["Global"]["stationsNames"]:
        seen[item["fr"].strip()].add(clean_ar(item["ar"]))
    good, bad = {}, {}
    for fr, ars in seen.items():
        ar = next(iter(ars))
        if len(ars) > 1:
            bad[fr] = "plusieurs noms arabes différents sur le site"
        elif not ARABIC.search(ar) or LATIN.search(ar):
            bad[fr] = "le « nom arabe » du site est écrit en lettres latines"
        elif not _ar_ok(fr, ar):
            bad[fr] = "le nom arabe du site ne reprend pas le numéro du libellé (nom d'un autre lieu)"
        else:
            good[fr] = ar
    return good, bad


def _cp1252(text):
    """Message lisible sur une console Windows (cp1252) : l'orchestrateur affiche les premiers éléments écartés."""
    text = text.replace("→", "->").replace("≤", "<=").replace("≥", ">=")
    return text.encode("cp1252", "replace").decode("cp1252")


def _fiche_names(doc, rows):
    """Noms des destinations (FR, AR) des tableaux « Depuis Tunis Sud / Nord » de la fiche, par libellé du site."""
    text = doc_path(doc, *THEME, "sntri.md").read_text(encoding="utf-8")
    section = text.split("### Depuis Tunis Sud", 1)[1].split("### Lignes ne passant pas par Tunis", 1)[0]
    found = defaultdict(set)
    for m in re.finditer(r"^\| ([^|\n]+?) \| (\d{3}(?:, \d{3})*) \|", section, re.M):
        dest = m.group(1).strip()
        mm = re.fullmatch(r"(.+?) \(([^)]*)\)", dest)
        fr, ar = (mm.group(1).strip(), mm.group(2).strip()) if mm else (dest, None)
        if "«" in fr:
            continue                                   # libellé du site entre guillemets : pas de nom propre
        ar = clean_ar(ar) if ar and _ar_ok(fr, clean_ar(ar)) else None
        for code in re.findall(r"\d{3}", m.group(2)):
            if code in rows:
                found[rows[code]["destination"]].add((fr, ar))
    return {label: next(iter(v)) for label, v in found.items() if len(v) == 1}


def _adjust(raw):
    """Heures en minutes du jour de service : on passe minuit quand l'heure recule de plus de 12 h."""
    out, prev = [], None
    for t in raw:
        if t is not None and prev is not None:
            while t - prev < -720:
                t += 1440
        out.append(t)
        prev = t if t is not None else prev
    return out


def _clean_direction(km, times):
    """Arrêts gardés dans un sens (ordre de parcours) : la plus longue suite d'heures croissantes allant du premier
    au dernier arrêt, sans vitesse impossible entre deux arrêts gardés (km du site) ; à égalité, celle qui a le
    moins de vitesses douteuses. None si les terminus eux-mêmes sont incompatibles."""
    n = len(times)
    if n < 2 or times[0] is None or times[-1] is None:
        return None

    def speed_ok(j, i, kmh):
        if km[j] is None or km[i] is None:
            return True
        return abs(km[i] - km[j]) <= (times[i] - times[j] + 5) / 60 * kmh     # heures arrondies à 5 min près

    best = {0: (1, 0, None)}
    for i in range(1, n):
        if times[i] is None:
            continue
        options = [(c + 1, v - (0 if speed_ok(j, i, SOFT_KMH) else 1), j) for j, (c, v, _) in best.items()
                   if times[j] <= times[i] and speed_ok(j, i, GROSS_KMH)]
        if options:
            best[i] = max(options)
    if n - 1 not in best:
        return None
    keep, cur = set(), n - 1
    while cur is not None:
        keep.add(cur)
        cur = best[cur][2]
    return keep


def _load_site(doc, rep):
    base = doc_path(doc, *THEME, "donnees")
    rows = {r["ligne"]: r for r in read_csv(base / "sntri-lignes.csv")}
    by_line = defaultdict(list)
    spellings = defaultdict(lambda: defaultdict(int))     # « EMB. JELMA » et « EMB.JELMA » : un même libellé
    for r in read_csv(base / "sntri-arrets-horaires.csv"):
        by_line[r["ligne"]].append(r)
        spellings[_compact(r["arret"])][r["arret"]] += 1
    canonical = {k: min(v, key=lambda s: (-v[s], s)) for k, v in spellings.items()}
    for key, variants in sorted(spellings.items()):
        if len(variants) > 1:
            rep["notes"].append(f"Libellés du site regroupés : {' / '.join(sorted(variants))} → {canonical[key]}")
    for rs in by_line.values():
        for r in rs:
            r["arret"] = canonical[_compact(r["arret"])]
    lines = []
    for code in sorted(rows, key=int):
        raw = sorted(by_line.get(code, []), key=lambda r: int(r["ordre"]))
        n = len(raw)
        if n < 2:
            rep["rejected"].append(f"Ligne {code} : moins de deux arrêts dans la base du site")
            continue
        site_km = [int(r["km_depuis_origine"]) for r in raw]
        km = list(site_km)
        for i in range(1, n - 1):
            a, k, b = site_km[i - 1], site_km[i], site_km[i + 1]
            if a < b and not a < k < b:
                rep["notes"].append(f"Ligne {code} : km de {raw[i]['arret']} incohérent ({k} entre {a} et {b}) : "
                                    f"seul l'horaire sert au contrôle de position")
                km[i] = None
        line = SLine(code, rows[code], [Stop(i, r["arret"], km[i], None, None) for i, r in enumerate(raw)])
        for direction, order, col in (("ALLER", list(range(n)), "heure_aller"),
                                      ("RETOUR", list(reversed(range(n))), "heure_retour")):
            times = _adjust([minutes(raw[i][col]) for i in order])
            keep = _clean_direction([km[i] for i in order], times)
            lost = [] if keep is None else [k for k in range(n) if k not in keep]
            if keep is None or len(lost) > (n - 2) / 3:
                listed = ", ".join(raw[i]["arret"] + " " + raw[i][col] for i in order)
                rep["notes"].append(f"Ligne {code} : sens {direction} non importé, heures du site incohérentes "
                                    f"({listed})")
                continue
            line.directions.append(direction)
            for k, i in enumerate(order):
                if k in keep:
                    setattr(line.stops[i], "go" if direction == "ALLER" else "back", times[k])
                else:
                    rep["notes"].append(f"Ligne {code} : {raw[i]['arret']} retiré du sens {direction}, heure "
                                        f"{raw[i][col]} incohérente avec les arrêts voisins")
        if not line.directions:
            rep["rejected"].append(f"Ligne {code} {rows[code]['intitule_site']} écartée : heures du site "
                                   f"incohérentes dans les deux sens")
            continue
        lines.append(line)
    return rows, lines


# --- Candidats (coordonnées) ---------------------------------------------------------------------------------------

@dataclass
class Cand:
    src: str            # REF | CARTO | GTFS | SRTM | REFX | OSM
    rank: int           # préférence (1 = meilleure)
    tier: int           # 1 : sources SNTRI ; 2 : autres sociétés
    name: str
    lat: float
    lon: float
    source: str         # OFFICIEL | OSM
    ref: str
    ar: str = None
    gare: bool = False
    match_name: str = None   # nom comparé aux libellés (défaut : name)
    own_name: bool = True    # False : la source reprend tel quel le libellé du site (GTFS 2020, cartographie ≥ 300)
    ar_words: tuple = ()     # nom arabe sans mots génériques (gares routières OSM)


def _float(text):
    return float(str(text).strip().replace(",", "."))


def _photo_years(text):
    years = sorted({datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).year
                    for ms in re.findall(r"(?<!\d)(1[4-7]\d{11})(?!\d)", text or "")})
    if not years:
        return "relevé 2018-2021"
    return f"relevé {years[0]}" if len(years) == 1 else f"relevé {years[0]}-{years[-1]}"


def _one(folder, pattern):
    files = sorted(Path(folder).glob(pattern))
    if not files:
        raise FileNotFoundError(f"Aucun fichier {pattern} dans {folder}")
    return files[0]


def _load_candidates(doc):
    dtn = doc_path(doc, *RAW, "data.transport.tn")
    cands = []

    # Référentiel national d'arrêts (ministère, relevés de terrain avec photos)
    path = _one(dtn / "referentiel-national-d-arret", "*.csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            societe = (r.get("Societe") or "").strip()
            if societe in ("SNCFT", "TRANSTU") or not societe:
                continue                               # gares ferroviaires et arrêts urbains du Grand Tunis
            try:
                lat, lon = _float(r["lat"]), _float(r["lon"])
            except (ValueError, TypeError):
                continue
            name = (r.get("Nom de la station") or "").strip()
            if not name or ARABIC.search(name):
                continue
            sntri = societe == "SNTRI"
            ref = (f"data.transport.tn, référentiel national d'arrêts ({_photo_years(r.get('joindre des photos'))}), "
                   f"arrêt {societe} « {name} », code {(r.get('Code-Station') or '').strip()}")
            cands.append(Cand("REF" if sntri else "REFX", 1 if sntri else 6, 1 if sntri else 2, name, lat, lon,
                              "OFFICIEL", ref, gare=(r.get("Type de la station") or "").startswith("Gare_Rout")))

    # Cartographie des stations SNTRI (publiée sur le portail le 2026-01-25, année des relevés non indiquée)
    path = _one(dtn / "cartographie-des-stations-sntri", "*.csv")
    for line in path.read_text(encoding="cp1252").splitlines()[1:]:
        parts = line.split(";")
        if len(parts) < 4 or not parts[2].strip():
            continue
        pid, name = parts[0].strip(), parts[1].strip()
        ref = (f"data.transport.tn, cartographie des stations SNTRI (jeu publié le 2026-01-25, année des relevés non "
               f"indiquée), point {pid} « {name} »")
        cands.append(Cand("CARTO", 2, 1, name, _float(parts[2]), _float(parts[3]), "OFFICIEL", ref,
                          own_name=int(pid) < 300))

    # GTFS SNTRI 2020 (fichiers du 2020-06-08)
    path = _one(dtn / "horaires-des-bus-de-la-sntri-gtfs1", "*.zip")
    with zipfile.ZipFile(path) as z:
        for r in csv.DictReader(io.StringIO(z.read("stops.txt").decode("utf-8-sig"))):
            ref = f"data.transport.tn, GTFS SNTRI 2020, arrêt {r['stop_id']} « {r['stop_name'].strip()} »"
            cands.append(Cand("GTFS", 3, 1, r["stop_name"].strip(), _float(r["stop_lat"]), _float(r["stop_lon"]),
                              "OFFICIEL", ref, own_name=False))

    # Stations de la SRT Médenine (noms FR et AR, coordonnées ; Médenine, Tataouine, Gabès, Sfax)
    path = _one(dtn / "liste-des-stations-de-la-srtm-et-leurs-positions-geographiques", "*.csv")
    with open(path, encoding="utf-16", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader, None)
        for r in reader:
            if len(r) < 7 or not r[5].strip():
                continue
            name = r[1].strip()
            ar = clean_ar(re.sub(r"^\s*وسط\s+", "", r[2]))
            ref = (f"data.transport.tn, stations de la SRT Médenine (jeu publié le 2026-01-25, année non indiquée), "
                   f"station {r[0].strip()} « {name} »")
            cands.append(Cand("SRTM", 5, 2, name, _float(r[5]), _float(r[6]), "OFFICIEL", ref,
                              ar=ar if _ar_ok(name, ar) else None))

    # Gares routières d'OpenStreetMap (extrait Geofabrik du 2026-10-13), sans les stations de louages ni les
    # stations urbaines de la Transtu ; nom comparé sans les mots génériques (« Gare routière de … »).
    path = doc_path(doc, *RAW, "osm", "geofabrik_2026-10-13", "bus_stations.geojson")
    for feat in json.loads(path.read_text(encoding="utf-8"))["features"]:
        props = feat["properties"]
        fr = props.get("name:fr") or (props.get("name") if LATIN.search(props.get("name") or "") else "") or ""
        ar = clean_ar(props.get("name:ar") or (props.get("name") if ARABIC.search(props.get("name") or "") else ""))
        everything = " ".join([fr, ar, props.get("operator", ""), props.get("network", "")]).lower()
        if not (fr or ar) or any(w in everything for w in OSM_EXCLUDE):
            continue
        lon, lat = feat["geometry"]["coordinates"]
        key = " ".join(w for w in norm_name(fr).split() if w not in FR_GENERIC)
        words = tuple(w for w in ar.split() if w not in AR_GENERIC)
        cands.append(Cand("OSM", 4, 1, fr or ar, lat, lon, "OSM",
                          f"OpenStreetMap {feat['id']} « {fr or ar} » (extrait Geofabrik du 2026-10-13)",
                          ar=ar or None, gare=True, match_name=key, ar_words=words))
    return cands


def _candidates_for(labels, cands, label_ars):
    """{libellé: [candidats]} ; les candidats hors de Tunisie sont comptés à part."""
    index = defaultdict(list)                   # première lettre du premier mot significatif -> (variante, candidat)
    by_ar = defaultdict(list)
    for c in cands:
        name = c.name if c.match_name is None else c.match_name
        for v in _variants(name) if name else []:
            index[_first(v)].append((v, c))
        if c.ar_words:
            by_ar[c.ar_words].append(c)
    out, outside = {}, defaultdict(list)
    for label in labels:
        if label in GARES:
            found = [c for c in cands if norm_name(c.name) in GARES[label]["names"]]
        else:
            found = []
            for key in sorted({_first(v) for v in _variants(label)}):
                for v, c in index.get(key, []):
                    if c not in found and _match(label, v):
                        found.append(c)
            for ar in sorted(label_ars.get(label, ())):
                found += [c for c in by_ar.get(tuple(ar.split()), []) if c not in found]
            extra = {_compact(a) for a in ALIASES.get(label, [])}
            if extra:
                found += [c for c in cands if _compact(c.name) in extra and c not in found]
        for c in found:
            if not in_tunisia(c.lat, c.lon):
                outside[label].append(c)
        out[label] = sorted((c for c in found if in_tunisia(c.lat, c.lon)), key=lambda c: (c.rank, c.ref))
    return out, outside


def _clusters(label, cands):
    """Regroupe les candidats proches (CLUSTER_KM) ; représentant = meilleur rang."""
    groups = []
    for c in cands:
        near = [g for g in groups if any(dist_m((c.lat, c.lon), (x.lat, x.lon)) <= CLUSTER_KM * 1000 for x in g)]
        merged = [c] + [x for g in near for x in g]
        groups = [g for g in groups if g not in near] + [merged]
    out = []
    for g in groups:
        g.sort(key=lambda c: (c.rank, not c.gare, c.ref))    # à rang égal, le point typé « gare routière »
        exact = label in GARES or any(c.own_name and _exact(label, c.name if c.match_name is None else c.match_name)
                                      for c in g)
        out.append(Cluster(g, 2 if exact else 1))
    return sorted(out, key=lambda cl: (cl.tier, cl.rep.rank, cl.key))


def _exact(label, name):
    """Même nom au sens strict (seuls les articles, la ponctuation et les lettres doublées diffèrent)."""
    def key(text):
        return "".join(_word(w) for w, _ in _significant(_tokens(text)))
    return any(key(v) == key(name) for v in _variants(label))


@dataclass
class Cluster:
    members: list
    strength: int = 1          # 2 : une source qui ne recopie pas le site porte exactement le libellé

    @property
    def rep(self):
        return self.members[0]

    @property
    def key(self):
        return self.rep.ref

    @property
    def tier(self):
        return min(c.tier for c in self.members)

    @property
    def pos(self):
        return (self.rep.lat, self.rep.lon)

    def sources(self):
        return sorted({c.src for c in self.members})

    @property
    def support(self):
        """Nombre de sources indépendantes : deux sources aux coordonnées identiques (à 2 m près, l'une copiée de
        l'autre, comme la cartographie SNTRI et le GTFS 2020) n'en font qu'une."""
        parent = {s: s for s in self.sources()}

        def root(s):
            while parent[s] != s:
                s = parent[s]
            return s
        for a in self.members:
            for b in self.members:
                if a.src < b.src and dist_m((a.lat, a.lon), (b.lat, b.lon)) <= 2:
                    parent[root(b.src)] = root(a.src)
        return len({root(s) for s in parent})


# --- Géocodage ----------------------------------------------------------------------------------------------------

def _limits(a, b):
    """(distance minimale, distance maximale) à vol d'oiseau en km entre deux arrêts d'une ligne ; None si rien ne
    borne. Maximum : km parcourus et durée du trajet (heures arrondies à 5 min) ; minimum : km parcourus (deux arrêts
    distants sur la route ne se confondent pas)."""
    high, low = [], 0.0
    if a.km is not None and b.km is not None:
        high.append(abs(a.km - b.km) * KM_FACTOR + KM_MARGIN)
        low = max(0.0, (abs(a.km - b.km) - LOW_MARGIN) / LOW_FACTOR)
    by_time = [(abs(x - y) + 5) / 60 * SPEED_KMH + TIME_MARGIN for x, y in ((a.go, b.go), (a.back, b.back))
               if x is not None and y is not None]
    if by_time:
        high.append(max(by_time))         # une seule des deux grilles suffit (coquilles possibles)
    return (low, min(high)) if high else None


def _fits(a, b, d):
    lim = _limits(a, b)
    return lim is None or lim[0] <= d <= lim[1]


class Geo:
    """Points retenus pour chaque libellé et occurrences (ligne, rang de l'arrêt) acceptées."""

    def __init__(self, lines, clusters):
        self.lines = {l.code: l for l in lines}
        self.clusters = clusters                         # libellé -> [Cluster] candidats
        self.occ = defaultdict(list)                     # libellé -> [(code, idx)]
        for l in lines:
            for s in l.stops:
                if s.go is not None or s.back is not None:      # desservi dans au moins un sens
                    self.occ[s.label].append((l.code, s.idx))
        self.pos = {}                                    # libellé -> [Cluster] retenus (plusieurs : homonymes)
        self.at = {}                                     # (code, idx) acceptée -> Cluster
        self.when = {}                                   # (code, idx) -> tour d'acceptation
        self.ambiguous = {}                              # libellé -> [Cluster] incompatibles
        self.tiebreaks = {}                              # libellé -> (retenu, écarté) départagés par la source
        self.unconfirmed = set()                         # occurrences acceptées sans voisin assez proche

    def stop(self, code, idx):
        return self.lines[code].stops[idx]

    def accept(self, occs, cluster, turn):
        positions = self.pos.setdefault(self.stop(*occs[0]).label, [])
        if all(c is not cluster for c in positions):
            positions.append(cluster)
        for o in occs:
            if o not in self.at:
                self.at[o] = cluster
                self.when[o] = turn

    def state(self):
        return frozenset((o, c.key) for o, c in self.at.items())

    def check(self, code, idx, pos):
        """(cohérent, borne la plus serrée en km) pour l'arrêt idx de la ligne placé en pos, d'après les arrêts
        déjà acceptés de la ligne ; borne None si aucun ne contraint la position."""
        me = self.stop(code, idx)
        tight = None
        for other in self.lines[code].stops:
            cl = self.at.get((code, other.idx))
            if other.idx == idx or cl is None:
                continue
            lim = _limits(me, other)
            if lim is None:
                continue
            d = dist_m(pos, cl.pos) / 1000
            if not lim[0] <= d <= lim[1]:
                return False, None
            tight = lim[1] if tight is None else min(tight, lim[1])
        return True, tight

    def ok(self, occ, cluster, confirm_km=CONFIRM_KM):
        """Cohérent et confirmé : un voisin accepté borne la position à moins de confirm_km."""
        consistent, tight = self.check(*occ, cluster.pos)
        return consistent and tight is not None and tight <= confirm_km

    def violations(self):
        """Paires d'arrêts acceptés incompatibles, comptées par occurrence."""
        count = defaultdict(int)
        for code, line in self.lines.items():
            acc = [s for s in line.stops if (code, s.idx) in self.at]
            for i, a in enumerate(acc):
                for b in acc[i + 1:]:
                    d = dist_m(self.at[(code, a.idx)].pos, self.at[(code, b.idx)].pos) / 1000
                    if not _fits(a, b, d):
                        count[(code, a.idx)] += 1
                        count[(code, b.idx)] += 1
        return count

    def resolve(self):
        """Retire une à une les occurrences les plus en conflit (à égalité : la plus récente) jusqu'à ce que tout
        soit cohérent. Les gares de Tunis ne sont jamais retirées."""
        while True:
            count = {k: n for k, n in self.violations().items() if self.stop(*k).label not in GARES}
            if not count:
                break
            # À égalité : l'arrêt le moins confirmé ailleurs sur le réseau, puis le plus récemment accepté.
            support = defaultdict(int)
            for o in self.at:
                support[self.stop(*o).label] += 1
            worst = min(count, key=lambda k: (-count[k], support[self.stop(*k).label], -self.when.get(k, 0),
                                              self.stop(*k).label, k))
            del self.at[worst]
        # Un point dont plus aucune occurrence n'est acceptée est oublié (il pourra être reproposé).
        for label in list(self.pos):
            if label in GARES:
                continue
            kept = [c for c in self.pos[label] if any(self.at.get(o) is c for o in self.occ[label])]
            if kept:
                self.pos[label] = kept
            else:
                del self.pos[label]


def _round(geo, tier):
    """Un tour de propagation, évalué sur l'état du début du tour : occurrences confirmées sur un point déjà retenu,
    puis nouveau point (premier point du libellé, ou homonyme à plus de HOMONYM_KM des points retenus)."""
    decisions = []
    for label in sorted(geo.occ):
        pending = [o for o in geo.occ[label] if o not in geo.at]
        if not pending:
            continue
        known = geo.pos.get(label, [])
        for cl in known:
            ok = [o for o in pending if geo.ok(o, cl)]
            if ok:
                decisions.append((cl, ok))
                pending = [o for o in pending if o not in ok]
        if not pending:
            continue
        scored = []
        for cl in geo.clusters.get(label, []):
            if cl.tier > tier or any(dist_m(cl.pos, k.pos) <= HOMONYM_KM * 1000 for k in known):
                continue
            ok = [o for o in pending if geo.ok(o, cl)]
            if ok:
                scored.append((len(ok), cl, ok))
        if not scored:
            continue
        # Le point confirmé sur le plus d'occurrences ; à égalité, celui dont une source indépendante du site porte
        # exactement le libellé, puis celui qu'appuient le plus de sources indépendantes, puis la meilleure source
        # (relevé terrain, cartographie SNTRI, GTFS 2020, OSM, autres sociétés).
        scored.sort(key=lambda s: (-s[0], -s[1].strength, -s[1].support, s[1].tier, s[1].rep.rank, s[1].key))
        n0, best, ok0 = scored[0]
        rivals = []
        for n, cl, ok in scored[1:]:
            d = dist_m(best.pos, cl.pos) / 1000
            if d <= SAME_PLACE_KM or not set(ok) & set(ok0) or (n, cl.strength, cl.support) != \
                    (n0, best.strength, best.support):
                continue                # même lieu, homonyme (autres lignes) ou nettement moins bien étayé
            if cl.rep.rank == best.rep.rank or d > TIE_KM:
                rivals.append(cl)
            else:
                geo.tiebreaks.setdefault(label, (best, cl))
        if rivals:
            geo.ambiguous[label] = [best] + rivals
            continue
        geo.ambiguous.pop(label, None)
        decisions.append((best, ok0))
    return decisions


def _propagate(geo, tier, turn):
    """Tours de propagation jusqu'à ce que plus rien de durable ne change ; renvoie le dernier numéro de tour."""
    seen = {geo.state()}
    while True:
        turn += 1
        decisions = _round(geo, tier)
        if not decisions:
            return turn
        for cl, ok in decisions:
            geo.accept(ok, cl, turn)
        geo.resolve()
        state = geo.state()
        if state in seen:
            return turn
        seen.add(state)


def _arbitrate(geo, turn):
    """Arbitrage final : chaque occurrence encore écartée d'un libellé placé est proposée à son point le moins en
    conflit sur la ligne, puis les conflits sont levés en retirant d'abord l'arrêt le plus en conflit, à égalité
    le moins confirmé sur le réseau (un arrêt aux km douteux ne fait pas tomber une ville desservie par dix
    lignes). Les occurrences sans voisin assez proche pour les borner (2 × CONFIRM_KM) ne sont pas gardées."""
    tentative = []
    for label in sorted(geo.pos):
        for o in geo.occ[label]:
            if o in geo.at:
                continue
            line = geo.lines[o[0]]

            def conflicts(cl, o=o, line=line):
                me = geo.stop(*o)
                return sum(1 for other in line.stops if (o[0], other.idx) in geo.at
                           and not _fits(me, other, dist_m(cl.pos, geo.at[(o[0], other.idx)].pos) / 1000))
            best = min(geo.pos[label], key=lambda cl: (conflicts(cl), cl.key))
            tentative.append((o, best))
    for o, cl in tentative:
        geo.accept([o], cl, turn)
    geo.resolve()
    for o, _ in tentative:
        if o in geo.at:
            consistent, tight = geo.check(*o, geo.at[o].pos)
            if tight is None or tight > 2 * CONFIRM_KM:
                del geo.at[o]
            elif tight > CONFIRM_KM:
                geo.unconfirmed.add(o)
    geo.resolve()


def _geocode(lines, cands_by_label):
    clusters = {label: _clusters(label, c) for label, c in cands_by_label.items() if c}
    geo = Geo(lines, clusters)

    # Points sûrs : gares de Tunis, et arrêts où relevé terrain SNTRI et cartographie / GTFS concordent seuls.
    for label, cls in sorted(clusters.items()):
        tier1 = [cl for cl in cls if cl.tier == 1]
        if not geo.occ.get(label) or not tier1:
            continue
        if label in GARES or (len(tier1) == 1 and "REF" in tier1[0].sources()
                              and {"CARTO", "GTFS"} & set(tier1[0].sources())):
            geo.accept(geo.occ[label], tier1[0], 0)
    geo.resolve()

    # Propagation : d'abord avec les seules sources SNTRI et OSM, puis avec les arrêts des autres sociétés ;
    # arbitrage des conflits, puis nouvelle propagation (des arrêts écartés à tort peuvent alors se placer).
    turn = _propagate(geo, 1, 0)
    turn = _propagate(geo, 2, turn)
    for _ in range(3):
        before = geo.state()
        _arbitrate(geo, turn + 1)
        turn = _propagate(geo, 2, turn + 1)
        if geo.state() == before:
            break
    for label in geo.pos:
        geo.ambiguous.pop(label, None)
    return geo


# --- Lieux ---------------------------------------------------------------------------------------------------------

def _build_places(geo, ar_site, ar_bad, fiche, rep):
    """Un lieu par point retenu ; deux libellés au même endroit (« EMB. JELMA » / « EMB.JELMA », « JERBA » /
    « HOUMT SOUK ») forment un seul lieu. Renvoie {(code, idx): lieu} et la liste des lieux."""
    lines_of = defaultdict(set)                      # (libellé, point) -> lignes
    for (code, idx), cl in geo.at.items():
        lines_of[(geo.stop(code, idx).label, cl.key)].add(code)
    items = {(label, cl.key): (label, cl) for label, cls in geo.pos.items() for cl in cls
             if lines_of.get((label, cl.key))}
    groups = []
    for key in sorted(items):
        p = items[key][1].pos
        near = [g for g in groups if any(dist_m(p, items[k][1].pos) <= MERGE_M for k in g)]
        merged = [key] + [k for g in near for k in g]
        groups = [g for g in groups if g not in near] + [merged]

    def weight(k):
        return -len(lines_of[k]), k
    groups = [sorted(g, key=weight) for g in groups]
    # Identifiants : SNTRI-<libellé> ; un homonyme (même libellé, autre lieu) reçoit -2, -3…
    by_base = defaultdict(list)
    for g in groups:
        by_base[slug(g[0][0])].append(g)
    ids = {}
    for base, gs in by_base.items():
        for n, g in enumerate(sorted(gs, key=lambda g: weight(g[0]))):
            ids[g[0]] = f"{NETWORK}-{base}" + (f"-{n + 1}" if n else "")

    places, by_item = [], {}
    for group in groups:
        labels = sorted({k[0] for k in group}, key=lambda l: (-sum(len(lines_of[k]) for k in group if k[0] == l), l))
        main, cl = group[0][0], items[group[0]][1]
        members = []
        for k in group:
            members += [c for c in items[k][1].members if c not in members]
        cand = cl.rep
        if main in GARES:
            g = GARES[main]
            osm_ar = max((c.ar for c in members if c.src == "OSM" and c.ar), key=lambda a: (len(a.split()), a),
                         default=None)                    # le nom le plus complet (« … باب عليوة »)
            fr, ar = g["fr"], osm_ar or ar_site.get(main)
            name_ref = "nom arabe : OpenStreetMap" if osm_ar else "nom arabe : sntri.com.tn"
            aliases = list(g["aliases"]) + [x for x in (ar_site.get(main),) if x]
        else:
            fiche_name = next((fiche[l] for l in labels if l in fiche), None)
            site_ar = next((ar_site[l] for l in labels if l in ar_site), None)
            srtm_ar = next((c.ar for c in members if c.src == "SRTM" and c.ar), None)
            if fiche_name:
                fr, ar = fiche_name[0], fiche_name[1] or site_ar or srtm_ar
                name_ref = "nom : fiche doc SNTRI (destinations)" + (
                    "" if fiche_name[1] else ", nom arabe : sntri.com.tn" if site_ar else
                    ", nom arabe : stations SRT Médenine" if srtm_ar else "")
            else:
                ar = site_ar or srtm_ar
                fr = _pretty(main, site_ar)
                name_ref = ("libellé et nom arabe : sntri.com.tn" if site_ar else
                            "libellé : sntri.com.tn, nom arabe : stations SRT Médenine" if srtm_ar else
                            "libellé : sntri.com.tn (pas de nom arabe sourcé)")
            aliases = []
            for x in labels + [c.name for c in members] + [site_ar, srtm_ar]:
                if x and x not in (fr, ar) and norm_name(x) != norm_name(fr) \
                        and norm_name(x) not in {norm_name(a) for a in aliases}:
                    aliases.append(x)
        pid = ids[group[0]]
        served = sorted({c for k in group for c in lines_of[k]}, key=int)
        note = (f"Libellé(s) du site : {', '.join(labels)}. Lignes : {', '.join(served)}. "
                f"Sources concordantes à moins de {CLUSTER_KM:g} km : {', '.join(cl.sources())}.")
        others = [o for o in geo.clusters.get(main, []) if all(o is not items[k][1] for k in group)
                  and dist_m(cl.pos, o.pos) > CLUSTER_KM * 1000]
        if others:
            note += " Autres points de même nom non retenus : " + "; ".join(
                f"{o.rep.src} « {o.rep.name} » à {dist_m(cl.pos, o.pos) / 1000:.1f} km" for o in others[:4]) + "."
        if main in geo.tiebreaks and geo.tiebreaks[main][0] is cl:
            alt = geo.tiebreaks[main][1]
            note += (f" Position départagée par la source : {alt.rep.src} « {alt.rep.name} » à "
                     f"{dist_m(cl.pos, alt.pos) / 1000:.1f} km était aussi compatible avec les lignes.")
            rep["notes"].append(f"Arrêt {main} ({pid}) : deux positions compatibles à "
                                f"{dist_m(cl.pos, alt.pos) / 1000:.1f} km, retenu {cand.src} plutôt que {alt.rep.src}")
        if len(geo.pos.get(main, [])) > 1:
            note += " Homonyme : le libellé désigne plusieurs lieux selon la ligne."
        status = "active" if ar else "draft"
        if not ar:
            reason = ar_bad.get(main, "aucun nom arabe dans les sources")
            note += f" Brouillon : {reason}."
            rep["rejected"].append(f"Arrêt {main} ({pid}) en brouillon : {reason} ; retiré des lignes actives")
        place = {"id": pid, "kind": "station" if main in GARES or any(c.gare for c in cl.members) else "stop",
                 "name": {"fr": fr, **({"ar": ar} if ar else {})}}
        if aliases:
            place["aliases"] = aliases
        place.update({
            "lat": round(cand.lat, 6), "lon": round(cand.lon, 6), "status": status,
            "provenance": prov(cand.source, f"Position : {cand.ref}. {name_ref[:1].upper()}{name_ref[1:]}."),
            "notes_internes": note,
        })
        places.append(place)
        for k in group:
            by_item[k] = place
    by_occ = {o: by_item[(geo.stop(*o).label, cl.key)] for o, cl in geo.at.items()}
    places.sort(key=lambda p: p["id"])
    return by_occ, places


# --- Lignes, grilles, tarifs ---------------------------------------------------------------------------------------

def _via(stops, termini, place_of, served):
    """Jusqu'à trois arrêts intermédiaires parmi les terminus d'autres lignes (villes desservies), les plus desservis,
    dans l'ordre du parcours."""
    mids, seen = [], set()
    for s in stops[1:-1]:
        pid = place_of(s)["id"]
        if s.label in termini and s.label not in GARES and pid not in seen and pid != place_of(stops[-1])["id"]:
            seen.add(pid)
            mids.append(s)
    top = sorted(mids, key=lambda s: (-served(s), s.idx))[:3]
    return [s for s in mids if s in top]


def _names(label, place):
    if label in GARES:
        return GARES[label]["short"], None
    return _short(place["name"]["fr"]), place["name"].get("ar")


def _cell(times):
    if len(times) == 1:
        return hhmm(times[0])
    return f"{hhmm(times[0])}/{hhmm(times[-1])}"


def _grid(header, calls, days=None, note=None):
    rows = [["stop_id", header], ["@jours", "-"]]
    if days:
        rows.append(["@days", days])
    if note:
        rows.append(["@notes", note])
    rows += [[pid, _cell(times)] for pid, times in calls]
    return "".join(",".join(r) + "\n" for r in rows)


def _segment_prices(sl, usable, place_of, calls, o_id, d_id, price):
    """Prix de chaque couple d'arrêts d'une ligne (millimes, dans le sens de circulation).

    Terminus–terminus : prix officiel du site. Ailleurs : prix au kilomètre de la ligne × km parcourus (km du site),
    arrondi à 0,100 DT, au moins 0,100 DT.
    """
    km_of = {}
    for s in sl.stops:
        if s.idx in usable and s.km is not None:
            km_of.setdefault(place_of(s)["id"], s.km)
    total = abs(km_of.get(d_id, 0) - km_of.get(o_id, 0))
    out = {}
    for c in calls.values():
        ids = [pid for pid, _ in c]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if {a, b} == {o_id, d_id}:
                    value = price
                elif total and a in km_of and b in km_of:
                    value = max(100, round(price * abs(km_of[b] - km_of[a]) / total / 100) * 100)
                else:
                    continue
                out[(a, b)] = value
    out[(o_id, d_id)] = out[(d_id, o_id)] = price
    return [{"from": a, "to": b, "price_millimes": {"PLEIN": v}} for (a, b), v in sorted(out.items())]


def _calls(stops, attr, place_of):
    """[(id du lieu, [heures])] dans l'ordre ; deux libellés consécutifs d'un même lieu = arrivée/départ."""
    out = []
    for s in stops:
        pid = place_of(s)["id"]
        t = getattr(s, attr)
        if out and out[-1][0] == pid:
            out[-1][1].append(t)
        else:
            out.append((pid, [t]))
    return out


def _feasible(stops, attr, place_of, weight):
    """Arrêts gardés dans un sens, une fois les lieux placés : la plus longue suite allant d'un terminus à l'autre
    sans trajet plus rapide que MAX_KMH à vol d'oiseau entre deux arrêts gardés consécutifs (heures du site
    arrondies : 3 min de marge) ; à égalité, celle qui garde les arrêts les plus desservis. None si impossible."""
    def ok(j, i):
        d = dist_m(*((place_of(stops[k])["lat"], place_of(stops[k])["lon"]) for k in (j, i))) / 1000
        return d <= (getattr(stops[i], attr) - getattr(stops[j], attr) + 3) / 60 * MAX_KMH

    best = {0: (1, weight(stops[0]), None)}
    for i in range(1, len(stops)):
        options = [(c + 1, w + weight(stops[i]), j) for j, (c, w, _) in best.items() if ok(j, i)]
        if options:
            best[i] = max(options)
    if len(stops) - 1 not in best:
        return None
    keep, cur = set(), len(stops) - 1
    while cur is not None:
        keep.add(cur)
        cur = best[cur][2]
    return keep


def _build_lines(site_lines, geo, by_occ, ar_site, outside, rep, src, written):
    termini = {l.row["origine"] for l in site_lines} | {l.row["destination"] for l in site_lines}
    lines_out, fares_out, trips = [], [], 0
    lines_at = defaultdict(set)                  # lieu -> lignes (poids des arrêts lors du contrôle des heures)
    for (code, _), place in by_occ.items():
        lines_at[place["id"]].add(code)
    for sl in site_lines:
        code, row = sl.code, sl.row
        intl = row["type"] == "international"
        status = "draft" if intl else "active"
        def place_of(s, code=code):
            return by_occ.get((code, s.idx))

        def served(s):
            return len(lines_at[place_of(s)["id"]])

        usable, dropped = set(), []
        for s in sl.stops:
            place = place_of(s)
            if s.go is None and s.back is None:
                dropped.append(f"{s.label} (heures du site incohérentes dans les deux sens)")
            elif place is None and s.label in geo.pos:
                dropped.append(f"{s.label} (lieu de ce nom incohérent avec les km et horaires de cette ligne)")
            elif place is None and s.label in outside:
                dropped.append(f"{s.label} (hors de Tunisie)")
            elif place is None:
                dropped.append(f"{s.label} (non géolocalisé)")
            elif status == "active" and place["status"] != "active":
                dropped.append(f"{s.label} (lieu {place['id']} en brouillon, sans nom arabe)")
            else:
                usable.add(s.idx)
        first, last = sl.stops[0], sl.stops[-1]
        # Ligne internationale : on garde la partie tunisienne (les lieux hors de Tunisie sont refusés).
        tunisian_end = intl and last.label not in geo.pos
        end = max((i for i in usable), default=None) if tunisian_end else last.idx
        if first.idx not in usable or end not in usable:
            rep["rejected"].append(f"Ligne {code} {row['intitule_site']} écartée : terminus non géolocalisé ou sans "
                                   f"nom arabe (arrêts retirés : {'; '.join(dropped) or 'aucun'})")
            continue

        calls = {}
        for direction in sl.directions:
            attr = "go" if direction == "ALLER" else "back"
            stops = [s for s in sl.stops if s.idx in usable and s.idx <= end and getattr(s, attr) is not None]
            if direction == "RETOUR":
                stops.reverse()
            if {stops[0].idx, stops[-1].idx} != {first.idx, end}:
                continue
            keep = _feasible(stops, attr, place_of, served)
            if keep is None:
                rep["notes"].append(f"Ligne {code} : sens {direction} non importé, heures du site impossibles entre "
                                    f"les terminus et leurs voisins")
                continue
            for k, s in enumerate(stops):
                if k not in keep:
                    rep["notes"].append(f"Ligne {code} : {s.label} retiré du sens {direction}, heure du site "
                                        f"{hhmm(getattr(s, attr))} impossible (plus de {MAX_KMH} km/h à vol d'oiseau "
                                        f"depuis ou vers l'arrêt voisin)")
            c = _calls([s for k, s in enumerate(stops) if k in keep], attr, place_of)
            if len(c) >= 2:
                calls[direction] = c
        if not calls:
            rep["rejected"].append(f"Ligne {code} {row['intitule_site']} écartée : aucun sens exploitable")
            continue
        if dropped:
            rep["notes"].append(f"Ligne {code} : {len(dropped)} arrêt(s) sur {len(sl.stops)} retiré(s) du parcours — "
                                f"{'; '.join(dropped)}")

        end_stop = sl.stops[end]
        o_fr, o_ar = _names(first.label, place_of(first))
        if tunisian_end:
            d_fr, d_ar = "Tripoli (Libye)", "طرابلس (ليبيا)"
        else:
            d_fr, d_ar = _names(last.label, place_of(last))
        o_ar = o_ar or ar_site.get(first.label)
        d_ar = d_ar or ar_site.get(last.label)
        name = {"fr": f"{o_fr} – {d_fr}", "ar": f"{o_ar} – {d_ar}"}
        via = _via([s for s in sl.stops if s.idx in usable and s.idx <= end], termini, place_of, served)
        line = {"id": f"{NETWORK}-{code}", "network": NETWORK, "mode": "BUS", "public_code": code, "name": name}
        if via:
            vfr = [_names(s.label, place_of(s))[0] for s in via]
            var = [_names(s.label, place_of(s))[1] for s in via]
            line["long_name"] = {
                "fr": f"{name['fr']} par {', '.join(vfr[:-1]) + ' et ' if len(vfr) > 1 else ''}{vfr[-1]}",
                "ar": f"{name['ar']} عبر {'، '.join(var)}"}

        rest = (row.get("jours_sans_service_opendata") or "").strip().lower()
        days, notes = None, {}
        if rest in WEEKDAY_CODES:
            day, fr_day, ar_day = WEEKDAY_CODES[rest]
            days = f"-{day}"
            notes["r"] = {"fr": f"Ne circule pas {fr_day}", "ar": f"لا يسير {ar_day}"}
        elif rest and not intl:
            rep["notes"].append(f"Ligne {code} : jours de service open data non interprétés (« {rest} »)")

        headsigns = {"ALLER": {"fr": d_fr, "ar": d_ar}, "RETOUR": {"fr": o_fr, "ar": o_ar}}
        line.update({
            "color": COLOR, "text_color": TEXT_COLOR, "status": status,
            "directions": [{"id": d, "headsign": headsigns[d]} for d in calls],
            "patterns": [{"id": d, "direction": d, "main": True, "stops": [p for p, _ in c], "shape": "auto"}
                         for d, c in calls.items()],
        })
        if notes:
            line["notes"] = notes
        line["day_codes"] = {"-": {"days": ["OUVRABLE", "SAMEDI", "DIMANCHE"],
                                   "label": {"fr": "Tous les jours", "ar": "كامل أيام الأسبوع"}}}
        updated = row["derniere_maj_base_site"]
        ref = (f"{SITE_REF}, ligne {code} « {row['intitule_site']} » ({row['distance_km']} km"
               f"{', base modifiée le ' + updated if updated else ''})")
        if days:
            ref += " ; jour sans service : jeu open data SNTRI « horaires des bus » (data.transport.tn, 2026-01-25)"
        if intl:
            ref += (f" ; ligne internationale : seule la partie tunisienne est décrite (jusqu'à {end_stop.label}, "
                    "les lieux hors de Tunisie sont refusés), le car continue vers Tripoli ; brouillon : aucune "
                    "annonce de service depuis 2021 et le jeu open data indique « selon la disponibilité du bus » "
                    "(fiche doc SNTRI, statut [I]) ; tarif Tunis – Tripoli (40,200 DT) non saisi, Tripoli n'étant "
                    "pas un lieu")
        line["schedule"] = {
            "kind": "timetable", "source_dir": f"timetables/{code}", "fallback": "inherit",
            "versions": [{"id": VERSION, "valid_from": VALID_FROM, "valid_to": VALID_TO,
                          "provenance": prov("OFFICIEL", ref)}],
        }
        fare_id = None
        if not intl:
            fare_id = f"FARE-{NETWORK}-{code}"
            o_id, d_id = place_of(first)["id"], place_of(last)["id"]
            price = dt_to_millimes(row["tarif_plein_dt"])
            pairs = _segment_prices(sl, usable, place_of, calls, o_id, d_id, price)
            fares_out.append((code, {
                "id": fare_id, "model": "od_pairs", "currency": "TND", "categories": ["PLEIN"],
                "versions": [{"valid_from": VALID_FROM, "pairs": pairs}],
                "provenance": prov("ESTIMATION", f"{SITE_REF}, ligne {code} : plein tarif terminus–terminus "
                                                 f"{price // 1000},{price % 1000:03d} DT (officiel), dans les deux "
                                                 f"sens ; entre arrêts intermédiaires (non publiés) : même prix au "
                                                 f"kilomètre × km du site, arrondi à 0,100 DT — le tarif SNTRI est "
                                                 f"proportionnel à la distance (doc/bus/regional-interurbain/sntri.md)"),
            }))
        line["fare"] = fare_id
        line["provenance"] = prov("OFFICIEL", ref)
        if intl:
            rep["notes"].append(f"Ligne {code} ({row['intitule_site']}) importée en brouillon, partie tunisienne "
                                f"seulement (jusqu'à {end_stop.label})")

        tdir = src / "networks" / "sntri" / "timetables" / code / VERSION / "NORMAL" / "TOUS"
        for d, c in calls.items():
            written.append(write_text(tdir / f"{d}.csv", _grid(f"{code}{d[0]}", c, days, "r" if notes else None)))
            trips += 1
        lines_out.append((code, line))
    return lines_out, fares_out, trips


# --- Écriture ------------------------------------------------------------------------------------------------------

def _network():
    return {
        "id": NETWORK,
        "name": {"fr": "SNTRI", "ar": "الشركة الوطنية للنقل بين المدن"},
        "long_name": {"fr": "Société nationale de transport interurbain", "ar": "الشركة الوطنية للنقل بين المدن"},
        "url": SITE_URL,
        "phone": PHONE,
        "timezone": "Africa/Tunis",
        "calendar": {
            "day_type_scheme": {"mon": "OUVRABLE", "tue": "OUVRABLE", "wed": "OUVRABLE", "thu": "OUVRABLE",
                                "fri": "OUVRABLE", "sat": "SAMEDI", "sun": "DIMANCHE"},
            "holiday_day_type": "DIMANCHE",
            # Aucune grille de Ramadan ni d'été publiée : repli sur la grille normale (une grille TOUS par ligne).
            "periods": ["RAMADAN", "ETE", "NORMAL"],
            "fallback": {"periods": {"RAMADAN": "NORMAL", "ETE": "NORMAL"},
                         "day_types": {"DIMANCHE": "SAMEDI", "SAMEDI": "OUVRABLE"}},
        },
        "status": "active",
        "provenance": prov("OFFICIEL", "sntri.com.tn (consulté le 2026-10-14) ; téléphone du service clients : "
                                       "fiche doc/bus/regional-interurbain/sntri.md"),
    }


def _existing(src):
    roots = [src / "places" / "sntri", src / "networks" / "sntri"]
    return {p for r in roots if r.exists() for p in r.rglob("*") if p.is_file()}


def run(doc, src):
    doc, src = Path(doc), Path(src)
    rep = {"written": [], "removed": [], "counts": {}, "rejected": [], "notes": [], "gares_tunis": {}}
    before = _existing(src)
    written = []

    rows, site_lines = _load_site(doc, rep)
    ar_site, ar_bad = _site_arabic(doc)
    fiche = _fiche_names(doc, rows)
    labels = sorted({s.label for l in site_lines for s in l.stops})
    label_ars = {l: {x for x in (ar_site.get(l), (fiche.get(l) or (None, None))[1]) if x} for l in labels}
    cands_by_label, outside = _candidates_for(labels, _load_candidates(doc), label_ars)
    geo = _geocode(site_lines, cands_by_label)

    by_occ, places = _build_places(geo, ar_site, ar_bad, fiche, rep)
    placed_labels = sorted({geo.stop(*o).label for o in by_occ})
    for label in labels:
        if label in placed_labels:
            continue
        if outside.get(label) and not cands_by_label.get(label):
            why = f"hors de Tunisie ({outside[label][0].ref})"
        elif not cands_by_label.get(label):
            why = ("aucun point de même nom dans le référentiel national, la cartographie SNTRI, le GTFS 2020, "
                   "les stations SRTM ni les gares routières OSM")
        elif label in geo.ambiguous:
            why = "positions possibles incompatibles : " + "; ".join(
                f"{c.rep.src} « {c.rep.name} » ({c.rep.lat:.4f}, {c.rep.lon:.4f})" for c in geo.ambiguous[label])
        else:
            why = "aucun point confirmé par l'ordre, les km et les heures des lignes (" + "; ".join(
                f"{c.rep.src} « {c.rep.name} » ({c.rep.lat:.4f}, {c.rep.lon:.4f})"
                for c in geo.clusters.get(label, [])[:5]) + ")"
        lines_of = sorted({c for c, _ in geo.occ.get(label, [])}, key=int)
        rep["rejected"].append(f"Arrêt {label} (lignes {', '.join(lines_of) or '-'}) non géolocalisé : {why}")

    for (code, idx), place in sorted(by_occ.items()):
        label = geo.stop(code, idx).label
        if label in GARES:
            rep["gares_tunis"].setdefault(label, place["id"])
    gare_ids = set(rep["gares_tunis"].values())
    written.append(write_yaml(src / "places" / "sntri" / "gares-tunis.yaml",
                              [p for p in places if p["id"] in gare_ids],
                              "sources-open-data/raw (référentiel national, OSM) et fiche SNTRI"))
    written.append(write_yaml(src / "places" / "sntri" / "arrets.yaml",
                              [p for p in places if p["id"] not in gare_ids], SRC_DOC))
    written.append(write_yaml(src / "networks" / "sntri" / "network.yaml", _network(),
                              "bus/regional-interurbain/sntri.md"))
    lines_out, fares_out, trips = _build_lines(site_lines, geo, by_occ, ar_site, outside, rep, src, written)
    for code, line in lines_out:
        written.append(write_yaml(src / "networks" / "sntri" / "lines" / f"ligne-{code}.yaml", line, SRC_DOC))
    for code, fare in fares_out:
        written.append(write_yaml(src / "networks" / "sntri" / "fares" / f"fare-sntri-{code}.yaml", fare,
                                  "bus/regional-interurbain/donnees/sntri-lignes.csv"))

    # Fichiers générés devenus inutiles (grilles CSV : seulement dans nos dossiers de version SITE-*)
    keep = {Path(p).resolve() for p in written}
    for path in sorted(before):
        if path.resolve() in keep:
            continue
        if path.suffix == ".yaml" and remove_generated(path):
            rep["removed"].append(_rel(path))
        elif path.suffix == ".csv" and any(part.startswith("SITE-") for part in path.parts):
            path.unlink()
            rep["removed"].append(_rel(path))
    tt = src / "networks" / "sntri" / "timetables"
    if tt.exists():
        for d in sorted((p for p in tt.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
            if not any(d.iterdir()):
                d.rmdir()

    rep["written"] = [_rel(p) for p in written]
    rep["rejected"] = [_cp1252(r) for r in rep["rejected"]]
    rep["counts"] = {
        "arrets": len(places),
        "arrets_actifs": sum(1 for p in places if p["status"] == "active"),
        "lignes": len(lines_out),
        "lignes_actives": sum(1 for _, l in lines_out if l["status"] == "active"),
        "voyages": trips,
        "arrets_geolocalises": len(placed_labels),
        "arrets_ecartes": len(labels) - len(placed_labels),
        "libelles_site": len(labels),
    }
    rep["notes"].insert(0, f"Validité retenue des grilles : {VALID_FROM} → {VALID_TO} (pas de fin publiée ; "
                           f"date de péremption des horaires de bus selon reference/modes.yaml, 180 jours)")
    return rep
