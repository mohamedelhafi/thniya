"""Chargement de data/src : YAML (sans conversion implicite des dates ni des heures) + validation de schéma."""

import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from citydata import paths


class _Loader(yaml.SafeLoader):
    """YAML sans surprises : les dates restent des chaînes, « 12:30 » n'est jamais un entier en base 60."""


_Loader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag not in (
        "tag:yaml.org,2002:timestamp", "tag:yaml.org,2002:int", "tag:yaml.org,2002:float")]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    re.compile(r"^(?:[-+]?(?:0|[1-9][0-9_]*)|0x[0-9a-fA-F_]+)$"),
    list("-+0123456789"),
)
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(r"^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+]?[0-9]+)?|\.[0-9_]+(?:[eE][-+]?[0-9]+)?)$"),
    list("-+0123456789."),
)


def read_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader)


# Correspondance chemin (relatif à data/src) -> schéma. Le premier motif qui correspond l'emporte.
SCHEMA_FOR = [
    ("reference/modes.yaml", "modes"),
    ("reference/feed.yaml", "feed"),
    ("calendar/periods.yaml", "periods"),
    ("calendar/time-bands.yaml", "time-bands"),
    ("calendar/years/*.yaml", "calendar-year"),
    ("places/hubs.yaml", "hubs"),
    ("places/*", "places"),
    ("networks/*/network.yaml", "network"),
    ("networks/*/lines/*.yaml", "line"),
    ("networks/*/fares/*.yaml", "fare"),
    ("networks/*/timetables/*", "timetable-derived"),
    ("coverage.yaml", "coverage"),
    ("transfers.yaml", "transfers"),
    ("alerts/*.yaml", "alert"),
]


def schema_for(rel):
    for pattern, schema in SCHEMA_FOR:
        if fnmatch.fnmatch(rel, pattern):
            return schema
    return None


def _registry(schemas_dir):
    resources = []
    for path in sorted(schemas_dir.glob("*.schema.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        resources.append((path.name, Resource.from_contents(contents, default_specification=DRAFT202012)))
    return Registry().with_resources(resources)


def _validators(schemas_dir):
    registry = _registry(schemas_dir)
    validators = {}
    for path in sorted(schemas_dir.glob("*.schema.json")):
        name = path.name.removesuffix(".schema.json")
        schema = json.loads(path.read_text(encoding="utf-8"))
        validators[name] = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
    return validators


@dataclass
class Dataset:
    root: Path
    modes: dict = field(default_factory=dict)
    feed: dict = field(default_factory=dict)
    periods: dict = field(default_factory=dict)
    years: dict = field(default_factory=dict)          # année -> liste d'événements
    time_bands: list = field(default_factory=list)
    places: dict = field(default_factory=dict)
    hubs: dict = field(default_factory=dict)
    networks: dict = field(default_factory=dict)
    lines: dict = field(default_factory=dict)
    fares: dict = field(default_factory=dict)
    coverage: list = field(default_factory=list)
    transfers: list = field(default_factory=list)
    alerts: list = field(default_factory=list)
    origin: dict = field(default_factory=dict)         # (type, id) -> fichier relatif


def _rel(path, root):
    return path.relative_to(root).as_posix()


def load(issues, src=None, schemas=None):
    """Charge et valide toutes les sources. Les erreurs vont dans `issues`."""
    src = Path(src or paths.SRC)
    validators = _validators(Path(schemas or paths.SCHEMAS))
    ds = Dataset(root=src)

    for path in sorted(src.rglob("*.yaml")):
        rel = _rel(path, src)
        schema = schema_for(rel)
        if schema is None:
            issues.error("FILE_UNKNOWN", "Fichier non reconnu (emplacement ou nom inattendu)", rel)
            continue
        try:
            data = read_yaml(path)
        except yaml.YAMLError as exc:
            issues.error("YAML_SYNTAX", f"YAML invalide : {exc}", rel)
            continue

        schema_errors = sorted(validators[schema].iter_errors(data), key=lambda e: list(e.absolute_path))
        for err in schema_errors[:20]:
            location = "/".join(str(p) for p in err.absolute_path)
            issues.error("SCHEMA", f"{location or '(racine)'} : {err.message}", rel)
        if schema_errors or schema == "timetable-derived":
            continue  # les grilles dérivées sont relues à la demande par timetable.py

        _store(ds, schema, data, rel, issues)

    return ds


def _put(ds, kind, table, item, rel, issues):
    key = item["id"]
    if key in table:
        issues.error("ID_DUPLICATE", f"{kind} {key} déjà défini dans {ds.origin[(kind, key)]}", rel)
        return
    item["_file"] = rel
    table[key] = item
    ds.origin[(kind, key)] = rel


def _store(ds, schema, data, rel, issues):
    if schema == "modes":
        for m in data:
            _put(ds, "mode", ds.modes, m, rel, issues)
    elif schema == "feed":
        ds.feed = data
    elif schema == "periods":
        for p in data:
            _put(ds, "période", ds.periods, p, rel, issues)
    elif schema == "calendar-year":
        if data["year"] in ds.years:
            issues.error("ID_DUPLICATE", f"Année {data['year']} définie deux fois", rel)
        for ev in data["events"]:
            ev["_file"] = rel
        ds.years[data["year"]] = data["events"]
    elif schema == "time-bands":
        for group in data:
            group["_file"] = rel
        ds.time_bands = data
    elif schema == "places":
        for p in data:
            _put(ds, "lieu", ds.places, p, rel, issues)
    elif schema == "hubs":
        for h in data:
            _put(ds, "pôle", ds.hubs, h, rel, issues)
    elif schema == "network":
        data["_dir"] = rel.rsplit("/", 1)[0]
        _put(ds, "réseau", ds.networks, data, rel, issues)
    elif schema == "line":
        data["_dir"] = rel.split("/lines/")[0]
        _put(ds, "ligne", ds.lines, data, rel, issues)
    elif schema == "fare":
        _put(ds, "tarif", ds.fares, data, rel, issues)
    elif schema == "coverage":
        for c in data:
            c["_file"] = rel
        ds.coverage = data
    elif schema == "transfers":
        ds.transfers = data or []
    elif schema == "alert":
        data["_file"] = rel
        ds.alerts.append(data)
