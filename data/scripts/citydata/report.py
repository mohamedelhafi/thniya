"""Rapport de qualité des données (specs/04c-generation-gtfs.md §5)."""

from collections import Counter
from datetime import timedelta

from citydata.timeutil import parse_date

PUBLISHED = ("active", "suspended")


def _age_days(today, verified_at):
    return (today - parse_date(verified_at)).days


def build(ds, issues, cal, trips, stats, gtfs_counts, alerts_applied, today, golden_lines, data_version):
    out = [f"# Rapport de qualité des données — {data_version}", "", f"Généré le {today.isoformat()}.", ""]

    # 1. Résumé
    out += ["## 1. Résumé", ""]
    by_mode = Counter()
    for line in ds.lines.values():
        by_mode[(line["mode"], line["status"])] += 1
    out += ["| Mode | Actives | Brouillons | Suspendues |", "|---|---|---|---|"]
    for mode in sorted({m for m, _ in by_mode}):
        out.append(f"| {mode} | {by_mode[(mode, 'active')]} | {by_mode[(mode, 'draft')]} | {by_mode[(mode, 'suspended')]} |")
    places = Counter(p["status"] for p in ds.places.values())
    out += ["", f"- Lieux : {places['active']} actifs, {places['draft']} en brouillon",
            f"- GTFS : {gtfs_counts['routes']} lignes, {gtfs_counts['stops']} arrêts, {gtfs_counts['trips']} voyages, "
            f"{gtfs_counts['stop_times']} passages, {gtfs_counts['frequencies']} fréquences, "
            f"{gtfs_counts['services']} services", ""]

    # 2. Erreurs
    out += ["## 2. Erreurs bloquantes", ""]
    out += [f"- `{i.code}` {i.message} — `{i.where}`" for i in issues.errors] or ["Aucune."]
    out.append("")

    # 3. Avertissements
    out += ["## 3. Avertissements", ""]
    warnings = issues.warnings
    if warnings:
        for code, n in Counter(i.code for i in warnings).most_common():
            out.append(f"### {code} ({n})")
            out += [f"- {i.message} — `{i.where}`" for i in warnings if i.code == code]
            out.append("")
    else:
        out += ["Aucun.", ""]

    # 4. Fraîcheur
    out += ["## 4. Fraîcheur des données", "", "| Ligne | Vérifiée le | Âge (jours) | Âge max | État |", "|---|---|---|---|---|"]
    for line in sorted(ds.lines.values(), key=lambda l: l["id"]):
        mode = ds.modes.get(line["mode"], {})
        kind = "frequency" if line["schedule"]["kind"] == "frequency" else "timetable"
        max_age = mode.get("max_data_age_days", {}).get(kind)
        age = _age_days(today, line["provenance"]["verified_at"])
        state = "⚠️ à revérifier" if max_age and age > max_age else "OK"
        out.append(f"| {line['id']} | {line['provenance']['verified_at']} | {age} | {max_age or '—'} | {state} |")
    out.append("")

    # 5. Calendrier
    out += ["## 5. Calendrier", "", "### Dates à confirmer dans les 60 prochains jours", ""]
    soon = [e for e in cal.events if e.status == "estimated" and today <= e.start <= today + timedelta(days=60)]
    out += [f"- {e.id} : {e.start.isoformat()}{' → ' + e.end.isoformat() if e.end != e.start else ''} "
            f"(estimé) — `{e.where}`" for e in sorted(soon, key=lambda e: e.start)] or ["Aucune."]
    out += ["", "### Replis de régime utilisés", ""]
    if stats.fallbacks:
        out += ["| Ligne | Régime du jour | Horaires utilisés | Jours |", "|---|---|---|---|"]
        out += [f"| {l} | {real} | {used} | {n} |" for (l, real, used), n in sorted(stats.fallbacks.items())]
    else:
        out.append("Aucun.")
    out += ["", "### Jours sans horaires", ""]
    if stats.no_version:
        for lid, dates in sorted(stats.no_version.items()):
            out.append(f"- {lid} : {len(dates)} jour(s), du {min(dates).isoformat()} au {max(dates).isoformat()} "
                       f"(aucune grille valide : nouvelle affiche à saisir ?)")
    else:
        out.append("Aucun.")
    out.append("")

    # 6. Couverture
    out += ["## 6. Couverture et traductions", ""]
    no_golden = [l["id"] for l in ds.lines.values() if l["status"] == "active" and l["id"] not in golden_lines]
    out += [f"- Lignes actives sans trajet de référence : {', '.join(sorted(no_golden)) or 'aucune'}"]
    no_ar = [p["id"] for p in ds.places.values() if p["status"] in PUBLISHED and not p["name"].get("ar")]
    out += [f"- Arrêts publiés sans nom arabe : {', '.join(no_ar) or 'aucun'}"]
    if alerts_applied:
        out += [f"- Perturbations appliquées : " + ", ".join(f"{k} ({v} voyages-jours retirés)"
                                                          for k, v in alerts_applied.items())]
    out.append("")
    return "\n".join(out)
