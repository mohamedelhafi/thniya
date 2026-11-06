"""Configuration du back-office Directus sur la base de saisie (specs/04d-base-de-saisie.md §4).

Idempotent : peut être relancé après chaque migration. Ne touche jamais aux données, seulement à la présentation
(libellés français, dossiers, interfaces de saisie, listes imbriquées) et au rôle « Opérateur de saisie ».
"""

import json
import os
import urllib.error
import urllib.request

FR = "fr-FR"

# Dossiers du menu : (id, libellé, icône)
FOLDERS = [
    ("f_reseau", "Réseau", "route"),
    ("f_lieux", "Lieux", "location_on"),
    ("f_tarifs", "Tarifs", "payments"),
    ("f_calendrier", "Calendrier", "calendar_month"),
    ("f_voyageurs", "Info voyageurs", "campaign"),
    ("f_parametres", "Paramètres", "settings"),
]

# collection : (dossier, libellé, icône, gabarit d'affichage, masquée dans le menu, champ de tri, note)
COLLECTIONS = {
    "network": ("f_reseau", "Réseaux", "corporate_fare", "{{name_fr}}", False, None,
                "Exploitants : SNCFT, Transtu, louages… Le calendrier dit quels jours roulent comme un dimanche."),
    "line": ("f_reseau", "Lignes", "route", "{{public_code}} · {{name_fr}}", False, None,
             "Lignes avec leurs directions, parcours et horaires (grilles ou fréquences)."),
    "line_direction": ("f_reseau", "Directions", "signpost", "{{id}} → {{headsign_fr}}", True, "position", None),
    "pattern": ("f_reseau", "Parcours", "timeline", "{{line_id}} · {{id}}", True, "position",
                "Suite ordonnée d'arrêts d'une ligne dans une direction."),
    "pattern_stop": ("f_reseau", "Arrêts du parcours", "pin_drop", "{{position}}. {{place_id.name_fr}}", True,
                     "position", None),
    "timetable_file": ("f_reseau", "Grilles horaires", "table_chart", "{{path}}", False, None,
                       "Grilles telles que sur les affiches : une colonne par train, une ligne par gare (CSV)."),
    "place": ("f_lieux", "Lieux et arrêts", "location_on", "{{name_fr}} · {{kind}}", False, None,
              "Gares, stations, arrêts de bus, stations de louage, points où l'on hèle un louage."),
    "hub": ("f_lieux", "Pôles d'échange", "hub", "{{name_fr}}", False, "position",
            "Lieux proches présentés comme un seul pôle (ex. Barcelone – Tunis Ville)."),
    "hub_member": ("f_lieux", "Membres du pôle", "link", "{{place_id.name_fr}}", True, "position", None),
    "fare": ("f_tarifs", "Tarifs", "payments", "{{id}} ({{model}})", False, None,
             "Prix en millimes (1 DT = 1000). flat = prix unique ; od_pairs = prix par trajet."),
    "fare_version": ("f_tarifs", "Versions de tarif", "history", "depuis le {{valid_from}}", True, None, None),
    "fare_pair": ("f_tarifs", "Prix par trajet", "swap_horiz", "{{from_place_id.name_fr}} → {{to_place_id.name_fr}}",
                  True, "position", None),
    "calendar_period": ("f_calendrier", "Périodes", "date_range", "{{name_fr}}", False, "position",
                        "Horaires normaux, d'été, de Ramadan…"),
    "calendar_event": ("f_calendrier", "Événements", "event", "{{name_fr}} ({{date_from}})", False, None,
                       "Fêtes et saisons datées, par année. Fêtes religieuses : statut « estimated » tant que non confirmées."),
    "time_band_group": ("f_calendrier", "Tranches horaires", "schedule", "{{periods}} / {{day_types}}", False,
                        "position", "Pointe du matin, journée, soirée… par période et type de jour."),
    "alert": ("f_voyageurs", "Perturbations", "campaign", "{{title_fr}}", False, "position",
              "Travaux, grèves, lignes suspendues : affichées dans l'app et appliquées aux horaires."),
    "coverage": ("f_voyageurs", "Couverture", "map", "{{name_fr}}", False, "position",
                 "Zones où les données sont complètes ou partielles."),
    "transfer": ("f_voyageurs", "Correspondances imposées", "transfer_within_a_station", None, False, "position",
                 None),
    "mode": ("f_parametres", "Modes", "commute", "{{name_fr}}", False, "position", None),
    "feed": ("f_parametres", "Éditeur du flux", "badge", "{{publisher_name}}", False, None, None),
    "publication": ("f_parametres", "Publications", "publish", "n°{{uid}} · {{status}} · {{data_version}}", False,
                    None, "Journal des générations GTFS à partir de la base (lecture seule)."),
}

LABELS = {
    "id": "Identifiant", "uid": "N°", "position": "Ordre", "name_fr": "Nom (français)", "name_ar": "Nom (arabe)",
    "long_name_fr": "Nom long (français)", "long_name_ar": "Nom long (arabe)", "aliases": "Autres noms",
    "area_fr": "Quartier (français)", "area_ar": "Quartier (arabe)", "geom": "Position", "kind": "Type",
    "parent_id": "Gare parente", "code": "Code", "platform_code": "Quai", "wheelchair": "Accessible en fauteuil",
    "status": "Statut", "provenance": "Provenance", "note": "Note interne", "extra": "Champs avancés",
    "source_file": "Fichier d'origine", "source_dir": "Dossier d'origine", "updated_at": "Modifié le",
    "network_id": "Réseau", "mode_id": "Mode", "public_code": "Code affiché", "color": "Couleur",
    "text_color": "Couleur du texte", "fare_id": "Tarif", "schedule": "Horaires", "line_id": "Ligne",
    "headsign_fr": "Destination (français)", "headsign_ar": "Destination (arabe)", "direction_id": "Direction",
    "main": "Parcours principal", "run_times": "Temps de parcours (min)", "pattern_uid": "Parcours",
    "place_id": "Lieu", "path": "Emplacement", "content": "Contenu", "hub_id": "Pôle", "model": "Modèle",
    "currency": "Devise", "categories": "Catégories", "valid_from": "Valable depuis",
    "price_millimes": "Prix (millimes)", "matrix_file": "Fichier matrice", "fare_version_uid": "Version",
    "from_place_id": "De", "to_place_id": "À", "year": "Année", "date_from": "Du", "date_to": "Au",
    "show_banner": "Bandeau dans l'app", "periods": "Périodes", "day_types": "Types de jour", "bands": "Tranches",
    "effect": "Effet", "severity": "Gravité", "title_fr": "Titre (français)", "title_ar": "Titre (arabe)",
    "body_fr": "Texte (français)", "body_ar": "Texte (arabe)", "url": "Lien", "scope": "Lignes / arrêts touchés",
    "active_periods": "Périodes actives", "level": "Niveau", "modes": "Modes", "gtfs_route_type": "Type GTFS",
    "schedule_kinds": "Types d'horaires", "shows_exact_times": "Heures exactes", "icon": "Icône",
    "default_color": "Couleur par défaut", "timezone": "Fuseau horaire", "calendar": "Calendrier",
    "phone": "Téléphone", "publisher_name": "Éditeur", "publisher_url": "Site", "default_lang": "Langue",
    "contact_email": "Courriel de contact", "data_version": "Version des données", "requested_by": "Demandée par",
    "started_at": "Début", "finished_at": "Fin", "errors": "Erreurs", "warnings": "Avertissements",
    "counts": "Volumes", "report": "Rapport", "lines": "Lignes", "line_ids": "Lignes desservies", "search": "Recherche",
    "directions": "Directions", "patterns": "Parcours", "stops": "Arrêts", "members": "Lieux du pôle",
    "versions": "Versions", "pairs": "Prix par trajet", "timetables": "Grilles horaires",
}

JSON_FIELDS = {"extra", "provenance", "schedule", "calendar", "run_times", "bands", "price_millimes", "scope",
               "active_periods", "counts"}
TAG_FIELDS = {"aliases", "schedule_kinds", "categories", "periods", "day_types", "modes"}
COLOR_FIELDS = {"color", "text_color", "default_color"}
ADVANCED = {"provenance", "extra", "source_file", "source_dir", "updated_at", "search", "position", "note"}
READONLY = {"updated_at", "search", "source_file", "source_dir", "uid"}
HIDDEN = {"search", "uid"}
CHOICES = {
    "status": ["draft", "active", "suspended", "archived"],
    ("place", "kind"): ["station", "platform", "stop", "louage_station", "louage_bay", "entrance", "hail_point"],
    "wheelchair": ["yes", "no", "unknown"],
    ("calendar_event", "kind"): ["holiday", "period_event", "special"],
    ("calendar_event", "status"): ["estimated", "confirmed"],
    "level": ["complete", "partial"],
    "effect": ["NO_SERVICE", "REDUCED_SERVICE", "DETOUR", "STOP_CLOSED", "DELAYS", "INFO"],
    "severity": ["info", "warning", "severe"],
    "model": ["flat", "zones", "od_matrix", "od_pairs", "sections"],
    ("publication", "status"): ["running", "ok", "failed"],
}
M2O_TEMPLATE = {"place": "{{name_fr}} ({{id}})", "line": "{{public_code}} · {{name_fr}}", "network": "{{name_fr}}",
                "mode": "{{name_fr}}", "fare": "{{id}}", "hub": "{{name_fr}}", "pattern": "{{line_id}} · {{id}}",
                "fare_version": "{{fare_id}} depuis {{valid_from}}"}

# Listes imbriquées (alias O2M) : (collection parent, champ alias, collection enfant, clé étrangère, tri)
O2M = [
    ("line", "directions", "line_direction", "line_id", "position"),
    ("line", "patterns", "pattern", "line_id", "position"),
    ("line", "timetables", "timetable_file", "line_id", None),
    ("pattern", "stops", "pattern_stop", "pattern_uid", "position"),
    ("hub", "members", "hub_member", "hub_id", "position"),
    ("fare", "versions", "fare_version", "fare_id", None),
    ("fare_version", "pairs", "fare_pair", "fare_version_uid", "position"),
    ("network", "lines", "line", "network_id", None),
]

DATA_COLLECTIONS = [c for c in COLLECTIONS if c != "publication"]

# Colonnes des listes par défaut (préréglages globaux) : ce qu'un opérateur veut voir d'un coup d'œil
LIST_COLUMNS = {
    "network": (["id", "name_fr", "name_ar", "status"], ["id"]),
    "line": (["public_code", "name_fr", "name_ar", "network_id", "mode_id", "status", "updated_at"], ["id"]),
    "timetable_file": (["path", "line_id", "kind", "updated_at"], ["path"]),
    "place": (["name_fr", "name_ar", "kind", "area_fr", "status", "updated_at"], ["name_fr"]),
    "hub": (["name_fr", "name_ar", "status"], ["position"]),
    "fare": (["id", "model", "network_id", "currency"], ["id"]),
    "calendar_period": (["name_fr", "name_ar", "show_banner"], ["position"]),
    "calendar_event": (["year", "name_fr", "date_from", "date_to", "kind", "status"], ["year", "date_from"]),
    "time_band_group": (["periods", "day_types"], ["position"]),
    "alert": (["title_fr", "effect", "severity", "status", "updated_at"], ["-updated_at"]),
    "coverage": (["name_fr", "level", "modes", "status"], ["position"]),
    "mode": (["name_fr", "name_ar", "icon", "default_color", "status"], ["position"]),
    "publication": (["uid", "status", "data_version", "errors", "warnings", "started_at", "requested_by"], ["-uid"]),
}


class Directus:
    def __init__(self, url, email, password):
        self.url = url.rstrip("/")
        self.token = None
        self.token = self.call("POST", "/auth/login", {"email": email, "password": password})["access_token"]

    def call(self, method, path, body=None, ok_codes=()):
        req = urllib.request.Request(self.url + path, method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {self.token}"} if self.token else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return json.loads(raw)["data"] if raw else None
        except urllib.error.HTTPError as e:
            if e.code in ok_codes:
                return None
            raise RuntimeError(f"{method} {path} → {e.code} {e.read()[:300].decode(errors='replace')}") from None


def _choices(collection, field):
    values = CHOICES.get((collection, field)) or CHOICES.get(field)
    return [{"text": v, "value": v} for v in values] if values else None


def _field_meta(collection, field, schema):
    meta = {"translations": [{"language": FR, "translation": LABELS.get(field, field)}],
            "readonly": field in READONLY, "hidden": field in HIDDEN}
    fk = (schema or {}).get("foreign_key_table")
    if field == "geom":
        geometry = "Polygon" if collection == "coverage" else "Point"
        meta.update(interface="map", special=["geometry"], width="full",
                    options={"geometryType": geometry,
                             "defaultView": {"center": {"lng": 10.18, "lat": 36.80}, "zoom": 11, "bearing": 0,
                                             "pitch": 0}})
    elif field in JSON_FIELDS:
        meta.update(interface="input-code", options={"language": "JSON", "lineNumber": True}, special=["cast-json"],
                    width="full")
    elif field in TAG_FIELDS:
        meta.update(interface="tags", special=["cast-json"], width="full", options={"alphabetize": False})
    elif field in COLOR_FIELDS:
        meta.update(interface="select-color", display="color", width="half")
    elif _choices(collection, field):
        meta.update(interface="select-dropdown", options={"choices": _choices(collection, field)}, width="half")
    elif fk:
        meta.update(interface="select-dropdown-m2o", special=["m2o"], width="half",
                    options={"template": M2O_TEMPLATE.get(fk, "{{id}}")},
                    display="related-values", display_options={"template": M2O_TEMPLATE.get(fk, "{{id}}")})
    elif field == "content":
        meta.update(interface="input-code", options={"language": "plaintext", "lineNumber": True}, width="full")
    elif field in ("report", "note"):
        meta.update(interface="input-multiline", width="full")
    elif field.endswith("_ar"):
        meta.update(interface="input", width="half", options={"font": "sans-serif", "placeholder": "بالعربية"})
    elif field.endswith("_fr") or field in ("id", "public_code", "code", "platform_code", "url", "phone"):
        meta.update(interface="input", width="half")
    elif field == "updated_at" or field.endswith("_at"):
        meta.update(interface="datetime", display="datetime", display_options={"relative": True}, width="half")
    return meta


def setup(url=None, email=None, password=None):
    url = url or os.environ.get("DIRECTUS_URL", "http://directus:8055")
    d = Directus(url, email or os.environ["DIRECTUS_ADMIN_EMAIL"], password or os.environ["DIRECTUS_ADMIN_PASSWORD"])

    d.call("PATCH", "/settings", {"project_name": "Thniya · saisie", "default_language": FR,
                                  "project_color": "#0F766E",
                                  "project_descriptor": "Données de transport du Grand Tunis",
                                  "default_appearance": "auto"})
    me = d.call("GET", "/users/me")
    d.call("PATCH", f"/users/{me['id']}", {"language": FR, "first_name": "Admin", "last_name": "Thniya"})

    existing = {c["collection"]: c for c in d.call("GET", "/collections")}
    for i, (fid, label, icon) in enumerate(FOLDERS):
        meta = {"icon": icon, "sort": i + 1, "collapse": "open",
                "translations": [{"language": FR, "translation": label, "singular": label, "plural": label}]}
        if fid in existing:
            d.call("PATCH", f"/collections/{fid}", {"meta": meta})
        else:
            d.call("POST", "/collections", {"collection": fid, "meta": meta, "schema": None})

    for i, (coll, (group, label, icon, template, hidden, sort, note)) in enumerate(COLLECTIONS.items()):
        if coll not in existing:
            print(f"  ! table {coll} absente de la base : lancer db-migrate")
            continue
        meta = {"group": group, "icon": icon, "display_template": template, "hidden": hidden, "sort": i + 1,
                "sort_field": sort, "note": note, "accountability": "all",
                "translations": [{"language": FR, "translation": label, "singular": label, "plural": label}]}
        d.call("PATCH", f"/collections/{coll}", {"meta": meta})

    fields = d.call("GET", "/fields")
    by_coll = {}
    for f in fields:
        by_coll.setdefault(f["collection"], {})[f["field"]] = f
    for coll in COLLECTIONS:
        for i, (name, f) in enumerate(by_coll.get(coll, {}).items()):
            if f.get("type") == "alias":
                continue
            meta = _field_meta(coll, name, f.get("schema"))
            # formulaire : identité et contenu d'abord, listes imbriquées ensuite, champs techniques à la fin
            meta["sort"] = (300 if name in ADVANCED else 0) + i + 1
            d.call("PATCH", f"/fields/{coll}/{name}", {"meta": meta})

    relations = {(r["collection"], r["field"]): r for r in d.call("GET", "/relations")}
    for parent, alias, child, fk, sort in O2M:
        alias_meta = {"special": ["o2m"], "interface": "list-o2m", "width": "full", "sort": 200 + len(alias),
                      "options": {"template": COLLECTIONS[child][3], "enableLink": True},
                      "translations": [{"language": FR, "translation": LABELS.get(alias, alias)}]}
        if alias not in by_coll.get(parent, {}):
            d.call("POST", f"/fields/{parent}", {"field": alias, "type": "alias", "meta": alias_meta})
        else:
            d.call("PATCH", f"/fields/{parent}/{alias}", {"meta": alias_meta})
        rel = relations.get((child, fk))
        meta = {"one_field": alias, "sort_field": sort, "one_deselect_action": "delete"}
        if rel and rel.get("meta"):
            d.call("PATCH", f"/relations/{child}/{fk}", {"meta": meta})
        else:
            d.call("PATCH", f"/relations/{child}/{fk}", {"meta": meta}, ok_codes=(403, 404))

    presets = {p["collection"]: p for p in d.call("GET", "/presets?filter[user][_null]=true&filter[role][_null]=true"
                                                       "&filter[bookmark][_null]=true&limit=-1")}
    for coll, (columns, sort) in LIST_COLUMNS.items():
        body = {"collection": coll, "layout": "tabular",
                "layout_query": {"tabular": {"fields": columns, "sort": sort, "limit": 100}},
                "layout_options": {"tabular": {"spacing": "compact"}}}
        if coll in presets:
            d.call("PATCH", f"/presets/{presets[coll]['id']}", body)
        else:
            d.call("POST", "/presets", body)

    _role(d)
    print(f"Back-office configuré : {len(COLLECTIONS)} collections, {len(O2M)} listes imbriquées ({url})")
    return 0


def _role(d):
    """Rôle « Opérateur de saisie » : modifie les données, lit le journal des publications, rien d'autre."""
    policies = {p["name"]: p for p in d.call("GET", "/policies?limit=-1")}
    name = "Saisie des données"
    if name in policies:
        policy_id = policies[name]["id"]
    else:
        policy_id = d.call("POST", "/policies", {"name": name, "icon": "edit_note", "app_access": True,
                                                 "admin_access": False, "enforce_tfa": False,
                                                 "description": "Créer, modifier et archiver les données de transport"})["id"]
        perms = [{"policy": policy_id, "collection": c, "action": a, "fields": ["*"], "permissions": {},
                  "validation": {}}
                 for c in DATA_COLLECTIONS for a in ("create", "read", "update", "delete")]
        perms += [{"policy": policy_id, "collection": c, "action": "read", "fields": ["*"], "permissions": {},
                   "validation": {}} for c in ("publication",)]
        d.call("POST", "/permissions", perms)
    roles = {r["name"]: r for r in d.call("GET", "/roles?limit=-1")}
    if "Opérateur de saisie" not in roles:
        d.call("POST", "/roles", {"name": "Opérateur de saisie", "icon": "edit_note",
                                  "description": "Saisie des lignes, arrêts, horaires et tarifs",
                                  "policies": [{"policy": policy_id}]})
