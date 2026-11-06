"""Tests du générateur sur un réseau fictif (data/scripts/tests/fixtures/src).

Calendrier de la fenêtre (janvier 2030) :
  06 dim · 07 lun · 08 mar (grève NO_SERVICE sur TST-T) · 09 mer (férié → DIMANCHE) · 12 sam · 13 dim
  14→20 Ramadan (priorité sur l'été qui commence le 17) · 21→31 été
"""

import csv
import io
import json
import zipfile
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from citydata import build, validate
from citydata.calendar import Calendar
from citydata.issues import Issues
from citydata.loader import load, read_yaml

NOW = datetime(2030, 1, 6, 12, 0, tzinfo=ZoneInfo("Africa/Tunis"))
START = date(2030, 1, 6)


def run_build(src, tmp_path, name="out"):
    out = tmp_path / name
    rc = build.build(start=START, days=20, src=src, out_dir=out, data_version="test", now=NOW)
    return rc, out


def read_gtfs(out):
    z = zipfile.ZipFile(out / "gtfs.zip")
    return {n: list(csv.DictReader(io.StringIO(z.read(n).decode("utf-8")))) for n in z.namelist()}


def dates_of(g, trip_id):
    sid = next(t["service_id"] for t in g["trips.txt"] if t["trip_id"] == trip_id)
    return {r["date"] for r in g["calendar_dates.txt"] if r["service_id"] == sid}


def stop_times(g, trip_id):
    return [r for r in g["stop_times.txt"] if r["trip_id"] == trip_id]


@pytest.fixture
def built(src, tmp_path):
    rc, out = run_build(src, tmp_path)
    assert rc == 0
    return read_gtfs(out), out


# --- Grilles et codes de jours -------------------------------------------------------------

def test_code_A_runs_except_sundays_and_holidays(built):
    g, _ = built
    d = dates_of(g, "TST-T:V1:NORMAL:TOUS:2")
    assert "20300107" in d and "20300112" in d          # lundi, samedi
    assert "20300106" not in d and "20300113" not in d  # dimanches
    assert "20300109" not in d                          # férié = dimanche


def test_code_B_runs_on_sundays_and_holidays(built):
    g, _ = built
    d = dates_of(g, "TST-T:V1:NORMAL:TOUS:3")
    assert {"20300106", "20300109", "20300113"} <= d
    assert "20300107" not in d


def test_no_service_alert_removes_the_day(built):
    g, _ = built
    assert "20300108" not in dates_of(g, "TST-T:V1:NORMAL:TOUS:1")
    assert "20300107" in dates_of(g, "TST-T:V1:NORMAL:TOUS:1")


def test_pass_through_and_after_midnight(built):
    g, _ = built
    st = stop_times(g, "TST-T:V1:NORMAL:TOUS:5")
    assert [r["stop_id"] for r in st] == ["TST-A", "TST-C"]   # « | » à Bêta : pas d'arrêt
    assert st[-1]["arrival_time"] == "24:30:00"


def test_distinct_arrival_and_departure(built):
    g, _ = built
    last = stop_times(g, "TST-T:V1:NORMAL:TOUS:2")[-1]
    assert (last["arrival_time"], last["departure_time"]) == ("07:20:00", "07:22:00")


# --- Calendrier, périodes, replis ----------------------------------------------------------

def test_calendar_resolution(src):
    issues = Issues()
    ds = load(issues, src=src)
    cal = Calendar(ds)
    net = ds.networks["TST"]
    assert cal.resolve(net, date(2030, 1, 9)).day_type == "DIMANCHE"        # férié un mercredi
    assert cal.resolve(net, date(2030, 1, 17)).period == "RAMADAN"          # Ramadan prioritaire sur l'été
    assert cal.resolve(net, date(2030, 1, 22)).period == "ETE"
    assert cal.resolve(net, date(2030, 1, 7)).period == "NORMAL"


def test_ramadan_falls_back_to_normal_grid(built):
    g, out = built
    assert "20300115" in dates_of(g, "TST-T:V1:NORMAL:TOUS:1")
    assert "Replis de régime utilisés" in (out / "report.md").read_text(encoding="utf-8")


def test_summer_grid_inherits_removes_shifts_and_adds(built):
    g, _ = built
    ids = {t["trip_id"] for t in g["trips.txt"]}
    assert "TST-T:V1:ETE:TOUS:2" not in ids                        # supprimé
    assert stop_times(g, "TST-T:V1:ETE:TOUS:1")[0]["departure_time"] == "06:10:00"   # décalé de +10
    assert "20300122" in dates_of(g, "TST-T:V1:ETE:TOUS:7")         # ajouté
    # La grille d'été ne couvre que le NORD : le SUD garde la grille normale ces jours-là
    assert "20300122" in dates_of(g, "TST-T:V1:NORMAL:TOUS:10")


# --- Fréquences (louages) ------------------------------------------------------------------

def test_frequency_trip_and_run_times(built):
    g, _ = built
    trip = "TST-L:NORMAL:OUVRABLE:POINTE:ALLER"
    freq = next(r for r in g["frequencies.txt"] if r["trip_id"] == trip)
    # intervalle de 10 min : OTP reçoit la moitié (attente moyenne), specs/05-otp.md S1
    assert (freq["start_time"], freq["end_time"], freq["headway_secs"], freq["exact_times"]) == \
        ("06:00:00", "09:00:00", "300", "0")
    assert [r["departure_time"] for r in stop_times(g, trip)] == ["06:00:00", "06:15:00", "06:40:00"]
    assert stop_times(g, trip)[1]["continuous_pickup"] == "0"
    assert "20300107" in dates_of(g, trip)


def test_frequency_band_without_service_and_service_hours(built):
    g, _ = built
    ids = {t["trip_id"] for t in g["trips.txt"]}
    assert "TST-L:RAMADAN:OUVRABLE:FTOUR:ALLER" not in ids
    soiree = next(r for r in g["frequencies.txt"] if r["trip_id"] == "TST-L:RAMADAN:OUVRABLE:SOIREE:ALLER")
    assert soiree["end_time"] == "25:01:00"   # dernier départ 25:00 inclus


def test_service_hours_by_direction(src, tmp_path):
    """Premiers et derniers départs propres à une direction (affiches Transtu) : prioritaires sur first/last."""
    line = src / "networks/tst/lines/louage.yaml"
    line.write_text(line.read_text(encoding="utf-8").replace(
        'service_hours: { first: "06:00", last: "21:00" }',
        'service_hours: { first: "06:00", last: "21:00", by_direction: { ALLER: { first: "07:30", last: "20:00" } } }'),
        encoding="utf-8")
    rc, out = run_build(src, tmp_path)
    assert rc == 0
    g = read_gtfs(out)
    pointe = next(r for r in g["frequencies.txt"] if r["trip_id"] == "TST-L:NORMAL:OUVRABLE:POINTE:ALLER")
    assert pointe["start_time"] == "07:30:00"
    meta = json.loads((out / "app-meta.json").read_text(encoding="utf-8"))
    # le contrat app-meta ne change pas : amplitude globale seulement
    assert meta["lines"]["TST-L"]["serviceHours"]["NORMAL:OUVRABLE"] == {"first": "06:00", "last": "21:00"}


def test_service_hours_unknown_direction_is_an_error(src):
    line = src / "networks/tst/lines/louage.yaml"
    line.write_text(line.read_text(encoding="utf-8").replace(
        'service_hours: { first: "06:00", last: "21:00" }',
        'service_hours: { first: "06:00", last: "21:00", by_direction: { RETOUR: { first: "07:30", last: "20:00" } } }'),
        encoding="utf-8")
    assert "REF_UNKNOWN" in _codes(src)


# --- Export et contrat app-meta ------------------------------------------------------------

def test_draft_entities_are_not_exported(built):
    g, _ = built
    assert "TST-D" not in {s["stop_id"] for s in g["stops.txt"]}


def test_arabic_translations_exported(built):
    g, _ = built
    assert {"table_name": "stops", "field_name": "stop_name", "language": "ar", "translation": "بيتا",
            "field_value": "Bêta"} in g["translations.txt"]


def test_app_meta_contract(built):
    _, out = built
    meta = json.loads((out / "app-meta.json").read_text(encoding="utf-8"))
    assert meta["dataVersion"] == "test"
    assert meta["lines"]["TST-L"]["frequencies"]["NORMAL:OUVRABLE"][0]["headwayMin"] == 10
    assert meta["calendar"]["TST"]["2030-01-09"]["holidays"][0]["id"] == "FERIE_TEST"
    assert meta["lines"]["TST-T"]["diagram"]["NORD"][0]["stop"] == "TST-A"
    assert "TST-L" in meta["stops"]["TST-B"]["lines"]


def test_build_is_deterministic(src, tmp_path):
    _, a = run_build(src, tmp_path, "a")
    _, b = run_build(src, tmp_path, "b")
    assert (a / "gtfs.zip").read_bytes() == (b / "gtfs.zip").read_bytes()
    assert (a / "app-meta.json").read_text(encoding="utf-8") == (b / "app-meta.json").read_text(encoding="utf-8")


# --- Erreurs de saisie ---------------------------------------------------------------------

def _codes(src):
    issues = Issues()
    ds = load(issues, src=src)
    if not issues.errors:
        validate.check(ds, issues)
        build._expand(ds, issues, START, date(2030, 1, 26), src)
    return {i.code for i in issues.errors}


def test_decreasing_time_is_an_error(src):
    grid = src / "networks/tst/timetables/train/V1/NORMAL/TOUS/SUD.csv"
    grid.write_text(grid.read_text(encoding="utf-8").replace("06:40", "06:20"), encoding="utf-8")
    assert "GRID_TIME_ORDER" in _codes(src)


def test_correction_must_match_grid(src):
    grid = src / "networks/tst/timetables/train/V1/NORMAL/TOUS/NORD.csv"
    grid.write_text(grid.read_text(encoding="utf-8").replace("06:10,07:10", "06:11,07:10"), encoding="utf-8")
    assert "CORRECTION_MISMATCH" in _codes(src)


def test_missing_arabic_name_is_an_error(src):
    places = src / "places/test/arrets.yaml"
    places.write_text(places.read_text(encoding="utf-8").replace(', ar: "بيتا"', ""), encoding="utf-8")
    assert "I18N_AR_MISSING" in _codes(src)


def test_time_band_gap_is_an_error(src):
    bands = src / "calendar/time-bands.yaml"
    bands.write_text(bands.read_text(encoding="utf-8").replace('from: "09:00", to: "26:00"',
                                                               'from: "10:00", to: "26:00"'), encoding="utf-8")
    assert "BANDS_GAP" in _codes(src)


def test_unknown_stop_in_pattern_is_an_error(src):
    line = src / "networks/tst/lines/train.yaml"
    line.write_text(line.read_text(encoding="utf-8").replace("[TST-A, TST-B, TST-C]", "[TST-A, TST-X, TST-C]"),
                    encoding="utf-8")
    assert "REF_UNKNOWN" in _codes(src)


def test_yaml_times_are_never_sexagesimal(tmp_path):
    f = tmp_path / "t.yaml"
    f.write_text("a: 12:30\nb: 2030-01-01\n", encoding="utf-8")
    assert read_yaml(f) == {"a": "12:30", "b": "2030-01-01"}
