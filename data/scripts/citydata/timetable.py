"""Lecture des grilles horaires (CSV « comme l'affiche ») et des grilles dérivées (YAML).

Voir specs/04-donnees-modele.md §9.
"""

import csv
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from citydata.loader import read_yaml
from citydata.timeutil import parse_time

PASS = "|"


@dataclass
class Call:
    stop: str
    arrival: int
    departure: int


@dataclass
class GridTrip:
    train: str
    calls: list                     # arrêts desservis, dans l'ordre
    passes: list = field(default_factory=list)   # gares traversées sans arrêt
    code: str = None                # code « jours de circulation » (@jours)
    pattern: str = None             # @pattern
    notes: list = field(default_factory=list)    # @notes
    days: str = None                # @days
    platform: str = None            # @platform

    def time_at(self, stop):
        return next((c for c in self.calls if c.stop == stop), None)


@dataclass
class Grid:
    path: str
    stops: list                     # ordre des lignes de la grille
    trips: list


def _cells(row):
    return [c.strip() for c in row]


def read_csv_grid(path, issues, rel):
    with open(path, encoding="utf-8", newline="") as f:
        rows = [_cells(r) for r in csv.reader(f) if any(c.strip() for c in r)]
    if not rows or rows[0][0] != "stop_id":
        issues.error("GRID_HEADER", "La première ligne doit commencer par « stop_id » puis les numéros de trains", rel)
        return None

    trains = rows[0][1:]
    if len(set(trains)) != len(trains):
        dupes = sorted({t for t in trains if trains.count(t) > 1})
        issues.error("GRID_DUP_TRAIN", f"Numéros de trains en double : {', '.join(dupes)}", rel)
    directives = {}
    stop_rows = []
    for line_no, row in enumerate(rows[1:], start=2):
        row = row + [""] * (len(trains) + 1 - len(row))
        if len(row) > len(trains) + 1:
            issues.error("GRID_WIDTH", f"Ligne {line_no} : {len(row) - 1} cellules pour {len(trains)} trains", rel)
        if row[0].startswith("@"):
            directives[row[0]] = row[1:len(trains) + 1]
        else:
            stop_rows.append((line_no, row[0], row[1:len(trains) + 1]))

    trips = []
    for col, train in enumerate(trains):
        calls, passes = [], []
        for line_no, stop, cells in stop_rows:
            cell = cells[col]
            where = f"{rel}:{line_no} (train {train})"
            if cell == "":
                continue
            if cell == PASS:
                passes.append(stop)
                continue
            try:
                if "/" in cell:
                    arr, dep = (parse_time(x) for x in cell.split("/", 1))
                else:
                    arr = dep = parse_time(cell)
            except ValueError as exc:
                issues.error("GRID_TIME", str(exc), where)
                continue
            if dep < arr:
                issues.error("GRID_TIME_ORDER", f"Départ avant l'arrivée à {stop}", where)
            if calls and arr < calls[-1].departure:
                issues.error("GRID_TIME_ORDER",
                             f"Heure décroissante : {stop} {cell} après {calls[-1].stop} "
                             f"{calls[-1].departure // 60:02d}:{calls[-1].departure % 60:02d}", where)
            calls.append(Call(stop, arr, dep))
        if len(calls) < 2:
            issues.error("GRID_TRIP_SHORT", f"Le train {train} dessert moins de 2 gares", rel)
            continue

        def directive(name):
            values = directives.get(name)
            return values[col] if values and values[col] else None

        notes = directive("@notes")
        trips.append(GridTrip(
            train=train, calls=calls, passes=passes,
            code=directive("@jours"), pattern=directive("@pattern"),
            notes=[n.strip() for n in notes.split(" ")] if notes else [],
            days=directive("@days"), platform=directive("@platform"),
        ))
    return Grid(rel, [s for _, s, _ in stop_rows], trips)


def read_grid(path, issues, version_dir, src_root, _depth=0):
    """Lit une grille CSV ou une grille dérivée (YAML : inherits / remove / add_file / shift)."""
    path = Path(path)
    rel = path.relative_to(src_root).as_posix()
    if path.suffix == ".csv":
        return read_csv_grid(path, issues, rel)

    if _depth > 5:
        issues.error("GRID_INHERIT_LOOP", "Héritage de grilles trop profond (boucle ?)", rel)
        return None
    spec = read_yaml(path)
    base_path = None
    for ext in (".csv", ".yaml"):
        candidate = Path(version_dir) / (spec["inherits"] + ext)
        if candidate.exists():
            base_path = candidate
            break
    if base_path is None:
        issues.error("GRID_INHERIT", f"Grille héritée introuvable : {spec['inherits']}", rel)
        return None
    base = read_grid(base_path, issues, version_dir, src_root, _depth + 1)
    if base is None:
        return None

    removed = set(spec.get("remove", []))
    unknown = removed - {t.train for t in base.trips}
    if unknown:
        issues.warning("GRID_REMOVE_UNKNOWN", f"Trains à supprimer absents de la grille de base : {sorted(unknown)}", rel)
    trips = [t for t in base.trips if t.train not in removed]

    for shift in spec.get("shift", []):
        for i, t in enumerate(trips):
            if t.train in shift["trains"]:
                m = shift["minutes"]
                trips[i] = replace(t, calls=[Call(c.stop, c.arrival + m, c.departure + m) for c in t.calls])

    if spec.get("add_file"):
        added = read_csv_grid(path.parent / spec["add_file"], issues, f"{rel} → {spec['add_file']}")
        if added:
            clash = {t.train for t in added.trips} & {t.train for t in trips}
            if clash:
                issues.error("GRID_DUP_TRAIN", f"Trains ajoutés déjà présents : {sorted(clash)}", rel)
            trips += added.trips
    return Grid(rel, base.stops, trips)


def discover_grids(network_dir, line, issues, src_root):
    """{ version_id: { (PERIODE, TYPE_JOUR): { DIRECTION: path } } } pour une ligne à horaires."""
    schedule = line["schedule"]
    base = Path(src_root) / network_dir / schedule.get("source_dir", "")
    found = {}
    for version in schedule.get("versions", []):
        vdir = base / version["id"]
        if not vdir.is_dir():
            issues.error("GRID_VERSION_DIR", f"Dossier de version absent : {vdir.relative_to(src_root).as_posix()}",
                         line["_file"])
            continue
        grids = {}
        for path in sorted(vdir.glob("*/*/*")):
            # Grille = fichier nommé d'après une direction (MAJUSCULES) ; les annexes (ajouts…) sont en minuscules
            if path.suffix not in (".csv", ".yaml") or not re.fullmatch(r"[A-Z0-9_]+", path.stem):
                continue
            period, day_type = path.parent.parent.name, path.parent.name
            grids.setdefault((period, day_type), {})[path.stem] = path
        found[version["id"]] = grids
    return found
