"""Outils partagés par les importeurs de la base de connaissances `doc/` (specs/04e-import-doc.md).

Chaque importeur lit les fichiers retravaillés de `doc/<thème>/donnees/` et écrit des fichiers `data/src` ordinaires,
validés ensuite par le générateur comme n'importe quelle saisie. Il ne possède que ses propres fichiers : ceux qui
commencent par l'en-tête GENERATED_BY.
"""

import csv
import math
import re
import unicodedata
from pathlib import Path

import yaml

from citydata import paths

DOC = paths.ROOT / "doc"
TODAY = "2026-10-14"
BY = "import-doc"
GENERATED_BY = "# Généré par `python -m citydata import-doc`"


def header(source):
    """En-tête des fichiers générés : d'où vient la donnée, et où la corriger."""
    return (f"{GENERATED_BY} depuis doc/{source}.\n"
            "# Ne pas modifier à la main : corriger la base de saisie (back-office) ou doc/, puis réimporter.\n")


# --- Lecture ------------------------------------------------------------------------------------

def read_csv(path):
    """CSV UTF-8 (avec ou sans BOM) → liste de dictionnaires ; cellules débarrassées des espaces."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(f)]


def doc_path(doc, *parts):
    p = Path(doc).joinpath(*parts)
    if not p.exists():
        raise FileNotFoundError(f"Fichier attendu dans doc/ : {p}")
    return p


# --- Écriture -----------------------------------------------------------------------------------

def dump_yaml(data):
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120)


def write_yaml(path, data, source):
    """Écrit un fichier data/src généré. Refuse d'écraser un fichier saisi à la main (sans l'en-tête)."""
    path = Path(path)
    if path.exists() and not is_generated(path):
        raise RuntimeError(f"{path} a été saisi à la main : l'import ne l'écrase pas")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header(source) + dump_yaml(data), encoding="utf-8", newline="\n")
    return path


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def is_generated(path):
    """Vrai si le fichier vient d'import-doc (en-tête GENERATED_BY), donc remplaçable."""
    try:
        with open(path, encoding="utf-8") as f:
            first = [f.readline(), f.readline()]
    except (OSError, UnicodeDecodeError):
        return False
    return any(l.startswith(GENERATED_BY) for l in first)


def remove_generated(path):
    """Supprime un fichier généré devenu inutile (jamais un fichier saisi à la main)."""
    path = Path(path)
    if path.exists() and is_generated(path):
        path.unlink()
        return True
    return False


# --- Provenance et statuts ----------------------------------------------------------------------

def prov(source, ref, verified_at=TODAY):
    """Provenance au format du modèle (OFFICIEL | TERRAIN | ESTIMATION | SIGNALEMENT | OSM)."""
    assert source in ("OFFICIEL", "TERRAIN", "ESTIMATION", "SIGNALEMENT", "OSM"), source
    return {"source": source, "ref": ref, "verified_at": verified_at, "by": BY}


# --- Textes et identifiants ---------------------------------------------------------------------

def slug(text, sep="-"):
    """« Hammam Lif (gare) » → « HAMMAM-LIF-GARE ». Identifiant stable : majuscules, ASCII, séparateur `-`."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9]+", sep, text).strip(sep).upper()
    return re.sub(re.escape(sep) + "+", sep, text) or "X"


def norm_name(text):
    """Nom comparable : minuscules, sans accents, sans ponctuation ni espaces multiples (rapprochement de sources)."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def clean_ar(text):
    """Arabe sans caractères invisibles (marques de direction, espaces insécables) ni espaces en trop."""
    text = re.sub(r"[​-‏‪-‮⁦-⁩﻿ ]", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def i18n(fr, ar):
    return {"fr": fr.strip(), "ar": clean_ar(ar)}


# --- Géographie et durées -----------------------------------------------------------------------

def dist_m(a, b):
    """Distance en mètres entre deux points (lat, lon), approximation équirectangulaire (précise à < 0,5 %)."""
    k = math.pi / 180
    x = (b[1] - a[1]) * k * math.cos((a[0] + b[0]) / 2 * k)
    y = (b[0] - a[0]) * k
    return math.hypot(x, y) * 6_371_000


def in_tunisia(lat, lon):
    return 30.2 <= lat <= 37.6 and 7.5 <= lon <= 11.7


def run_minutes(points, speed_kmh, dwell_min, detour=1.2):
    """Durées estimées de chaque tronçon (min) : distance à vol d'oiseau × détour, à vitesse moyenne, + arrêt.

    Arrondi sur le cumul pour ne pas gonfler les lignes à arrêts rapprochés ; jamais moins d'une minute.
    """
    out, cumul, done = [], 0.0, 0
    for a, b in zip(points, points[1:]):
        cumul += dist_m(a, b) * detour / 1000 / speed_kmh * 60 + dwell_min
        seg = max(1, round(cumul) - done)
        out.append(seg)
        done += seg
    return out


def scaled(values, factor):
    """Durées × facteur (profil chargé), arrondies sur le cumul."""
    out, cumul, done = [], 0.0, 0
    for v in values:
        cumul += v * factor
        seg = max(1, round(cumul) - done)
        out.append(seg)
        done += seg
    return out


def hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def minutes(text):
    """« 05:30 » → 330 ; « 24:15 » → 1455 ; vide → None."""
    if not text:
        return None
    m = re.fullmatch(r"(\d{1,2})[:h](\d{2})", text.strip())
    if not m:
        raise ValueError(f"Heure illisible : {text!r}")
    return int(m.group(1)) * 60 + int(m.group(2))


def dt_to_millimes(text):
    """« 0,700 » ou « 0.7 » (dinars) → 700 millimes."""
    value = float(text.replace(",", ".").replace(" ", ""))
    return int(round(value * 1000))
