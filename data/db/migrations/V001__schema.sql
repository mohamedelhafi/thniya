-- Thniya : base de saisie des données de transport (specs/04d-base-de-saisie.md, ADR-007).
-- Source de vérité éditée dans le back-office ; le générateur l'exporte vers le format data/src puis produit le GTFS.
-- Règles :
--   * colonnes explicites pour tout ce qui se saisit ou se recherche ; « extra » (jsonb) garde le reste à l'identique,
--     pour qu'aucune information des sources ne se perde à l'import ou à l'export ;
--   * clé primaire sur une seule colonne (exigence du back-office Directus) : identifiant métier pour les entités,
--     « uid » technique pour les lignes de détail, avec une contrainte d'unicité sur la clé métier ;
--   * géométries en WGS 84 (SRID 4326), index GiST ; recherche plein texte tolérante (pg_trgm + unaccent).

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Normalisation pour la recherche : minuscules, sans accents (« Mégrine » = « megrine »)
CREATE OR REPLACE FUNCTION thniya_norm(t text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    AS $$ SELECT lower(public.unaccent('public.unaccent'::regdictionary, coalesce(t, ''))) $$;

CREATE OR REPLACE FUNCTION thniya_touch() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

-- ---------------------------------------------------------------------------------------------------------------
-- Référentiels
-- ---------------------------------------------------------------------------------------------------------------

CREATE TABLE feed (
    id              text PRIMARY KEY DEFAULT 'feed' CHECK (id = 'feed'),
    publisher_name  text NOT NULL,
    publisher_url   text NOT NULL,
    default_lang    text NOT NULL DEFAULT 'fr',
    contact_email   text,
    extra           jsonb NOT NULL DEFAULT '{}',
    updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE feed IS 'Éditeur du flux GTFS (feed_info.txt). Une seule ligne.';

CREATE TABLE mode (
    id                 text PRIMARY KEY,
    position           int NOT NULL DEFAULT 0,
    name_fr            text NOT NULL,
    name_ar            text,
    gtfs_route_type    int NOT NULL,
    schedule_kinds     text[] NOT NULL DEFAULT '{}',
    shows_exact_times  boolean NOT NULL DEFAULT true,
    icon               text NOT NULL,
    default_color      text CHECK (default_color ~ '^#[0-9A-Fa-f]{6}$'),
    status             text NOT NULL DEFAULT 'active',
    extra              jsonb NOT NULL DEFAULT '{}',
    updated_at         timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE mode IS 'Modes de transport (train, métro, bus, louage…) et leur comportement.';

-- ---------------------------------------------------------------------------------------------------------------
-- Calendrier : périodes (normal, été, Ramadan…), événements datés par année, tranches horaires
-- ---------------------------------------------------------------------------------------------------------------

CREATE TABLE calendar_period (
    id          text PRIMARY KEY,
    position    int NOT NULL DEFAULT 0,
    name_fr     text NOT NULL,
    name_ar     text,
    show_banner boolean NOT NULL DEFAULT false,
    extra       jsonb NOT NULL DEFAULT '{}',
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE calendar_period IS 'Périodes horaires. extra : default, from_events, from_events_all, extend.';

CREATE TABLE calendar_event (
    uid         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    year        int NOT NULL,
    id          text NOT NULL,
    position    int NOT NULL DEFAULT 0,
    kind        text NOT NULL,
    date_from   date NOT NULL,
    date_to     date NOT NULL,
    status      text NOT NULL,
    name_fr     text NOT NULL,
    name_ar     text,
    extra       jsonb NOT NULL DEFAULT '{}',
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (year, id),
    CHECK (date_to >= date_from)
);
COMMENT ON TABLE calendar_event IS 'Fêtes, Ramadan, saisons… par année. date_from = date_to pour un événement d''un jour.';

CREATE TABLE time_band_group (
    uid         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    position    int NOT NULL UNIQUE,
    periods     text[] NOT NULL,
    day_types   text[] NOT NULL,
    bands       jsonb NOT NULL,
    extra       jsonb NOT NULL DEFAULT '{}',
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE time_band_group IS 'Tranches horaires (pointe, journée…) par période et type de jour, de 00:00 à 26:00.';

-- ---------------------------------------------------------------------------------------------------------------
-- Réseaux et lieux
-- ---------------------------------------------------------------------------------------------------------------

CREATE TABLE network (
    id            text PRIMARY KEY,
    name_fr       text NOT NULL,
    name_ar       text,
    long_name_fr  text,
    long_name_ar  text,
    url           text,
    phone         text,
    timezone      text NOT NULL DEFAULT 'Africa/Tunis',
    calendar      jsonb NOT NULL,
    status        text NOT NULL DEFAULT 'active',
    provenance    jsonb NOT NULL,
    extra         jsonb NOT NULL DEFAULT '{}',
    source_dir    text,
    updated_at    timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE network IS 'Exploitants (SNCFT, Transtu, louages…). calendar : types de jour, périodes applicables, replis.';

CREATE TABLE place (
    id             text PRIMARY KEY,
    position       int NOT NULL DEFAULT 0,
    kind           text NOT NULL,
    name_fr        text NOT NULL,
    name_ar        text,
    aliases        text[] NOT NULL DEFAULT '{}',
    area_fr        text,
    area_ar        text,
    geom           geometry(Point, 4326) NOT NULL,
    parent_id      text REFERENCES place (id) DEFERRABLE INITIALLY DEFERRED,
    code           text,
    platform_code  text,
    wheelchair     text,
    status         text NOT NULL DEFAULT 'active',
    provenance     jsonb NOT NULL,
    note           text,
    extra          jsonb NOT NULL DEFAULT '{}',
    source_file    text,
    search         text,
    updated_at     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE place IS 'Gares, stations, arrêts, stations de louage, points de montée. geom : position WGS 84.';
COMMENT ON COLUMN place.search IS 'Noms et alias normalisés (calculé), pour la recherche tolérante.';
CREATE INDEX place_geom_idx ON place USING gist (geom);
CREATE INDEX place_search_idx ON place USING gin (search gin_trgm_ops);
CREATE INDEX place_parent_idx ON place (parent_id);
CREATE INDEX place_kind_idx ON place (kind);

CREATE OR REPLACE FUNCTION place_search_refresh() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.search := thniya_norm(concat_ws(' ', NEW.id, NEW.name_fr, NEW.name_ar, NEW.area_fr,
                                        array_to_string(NEW.aliases, ' ')));
    RETURN NEW;
END $$;
CREATE TRIGGER place_search BEFORE INSERT OR UPDATE ON place FOR EACH ROW EXECUTE FUNCTION place_search_refresh();

CREATE TABLE hub (
    id          text PRIMARY KEY,
    position    int NOT NULL DEFAULT 0,
    name_fr     text NOT NULL,
    name_ar     text,
    aliases     text[] NOT NULL DEFAULT '{}',
    status      text NOT NULL DEFAULT 'active',
    extra       jsonb NOT NULL DEFAULT '{}',
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE hub IS 'Pôles d''échange : plusieurs lieux proches présentés comme un seul (Barcelone – Tunis Ville).';

CREATE TABLE hub_member (
    uid       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hub_id    text NOT NULL REFERENCES hub (id) ON DELETE CASCADE,
    place_id  text NOT NULL REFERENCES place (id),
    position  int NOT NULL DEFAULT 0,
    UNIQUE (hub_id, place_id)
);

-- ---------------------------------------------------------------------------------------------------------------
-- Tarifs
-- ---------------------------------------------------------------------------------------------------------------

CREATE TABLE fare (
    id           text PRIMARY KEY,
    network_id   text REFERENCES network (id),
    model        text NOT NULL CHECK (model IN ('flat', 'zones', 'od_matrix', 'od_pairs', 'sections')),
    currency     text NOT NULL DEFAULT 'TND',
    categories   text[] NOT NULL DEFAULT '{}',
    provenance   jsonb NOT NULL,
    extra        jsonb NOT NULL DEFAULT '{}',
    source_file  text,
    updated_at   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE fare IS 'Tarifs. Prix en millimes (1 DT = 1000 millimes), par catégorie (PLEIN, REDUIT…).';

CREATE TABLE fare_version (
    uid             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fare_id         text NOT NULL REFERENCES fare (id) ON DELETE CASCADE,
    valid_from      date NOT NULL,
    price_millimes  jsonb,
    matrix_file     text,
    extra           jsonb NOT NULL DEFAULT '{}',
    UNIQUE (fare_id, valid_from)
);

CREATE TABLE fare_pair (
    uid               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fare_version_uid  bigint NOT NULL REFERENCES fare_version (uid) ON DELETE CASCADE,
    position          int NOT NULL DEFAULT 0,
    from_place_id     text NOT NULL REFERENCES place (id),
    to_place_id       text NOT NULL REFERENCES place (id),
    price_millimes    jsonb NOT NULL
);
CREATE INDEX fare_pair_version_idx ON fare_pair (fare_version_uid);

-- ---------------------------------------------------------------------------------------------------------------
-- Lignes, directions, parcours
-- ---------------------------------------------------------------------------------------------------------------

CREATE TABLE line (
    id            text PRIMARY KEY,
    network_id    text NOT NULL REFERENCES network (id),
    mode_id       text NOT NULL REFERENCES mode (id),
    public_code   text NOT NULL,
    name_fr       text NOT NULL,
    name_ar       text,
    long_name_fr  text,
    long_name_ar  text,
    color         text CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
    text_color    text CHECK (text_color ~ '^#[0-9A-Fa-f]{6}$'),
    status        text NOT NULL DEFAULT 'active',
    fare_id       text REFERENCES fare (id),
    schedule      jsonb NOT NULL,
    provenance    jsonb NOT NULL,
    extra         jsonb NOT NULL DEFAULT '{}',
    source_file   text,
    updated_at    timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE line IS 'Lignes. schedule : grilles (versions) ou fréquences (régimes, tranches) — voir specs/04b.';
CREATE INDEX line_network_idx ON line (network_id);

CREATE TABLE line_direction (
    uid               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    line_id           text NOT NULL REFERENCES line (id) ON DELETE CASCADE,
    id                text NOT NULL,
    position          int NOT NULL DEFAULT 0,
    headsign_fr       text NOT NULL,
    headsign_ar       text,
    extra             jsonb NOT NULL DEFAULT '{}',
    UNIQUE (line_id, id)
);

CREATE TABLE pattern (
    uid           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    line_id       text NOT NULL REFERENCES line (id) ON DELETE CASCADE,
    id            text NOT NULL,
    position      int NOT NULL DEFAULT 0,
    direction_id  text NOT NULL,
    main          boolean NOT NULL DEFAULT false,
    run_times     jsonb,
    extra         jsonb NOT NULL DEFAULT '{}',
    UNIQUE (line_id, id)
);
COMMENT ON TABLE pattern IS 'Parcours (suite d''arrêts) d''une ligne dans une direction. run_times : minutes par tronçon et par profil.';

CREATE TABLE pattern_stop (
    uid          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pattern_uid  bigint NOT NULL REFERENCES pattern (uid) ON DELETE CASCADE,
    position     int NOT NULL,
    place_id     text NOT NULL REFERENCES place (id),
    extra        jsonb NOT NULL DEFAULT '{}'
);
COMMENT ON COLUMN pattern_stop.extra IS 'Options de desserte : continuous (louage hélé), pickup, dropoff…';
CREATE INDEX pattern_stop_pattern_idx ON pattern_stop (pattern_uid, position);
CREATE INDEX pattern_stop_place_idx ON pattern_stop (place_id);

-- Grilles horaires telles que sur les affiches (CSV) et grilles dérivées (YAML), stockées à l'identique.
CREATE TABLE timetable_file (
    path        text PRIMARY KEY,
    network_id  text REFERENCES network (id),
    line_id     text REFERENCES line (id) ON DELETE SET NULL,
    kind        text NOT NULL CHECK (kind IN ('csv', 'yaml')),
    content     text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE timetable_file IS 'Grilles horaires. path : emplacement dans data/src (réseau/timetables/ligne/VERSION/PÉRIODE/JOUR/DIRECTION.csv).';

-- ---------------------------------------------------------------------------------------------------------------
-- Correspondances, couverture, alertes
-- ---------------------------------------------------------------------------------------------------------------

CREATE TABLE transfer (
    uid            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    position       int NOT NULL DEFAULT 0,
    from_place_id  text REFERENCES place (id),
    to_place_id    text REFERENCES place (id),
    extra          jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE coverage (
    id          text PRIMARY KEY,
    position    int NOT NULL DEFAULT 0,
    name_fr     text NOT NULL,
    name_ar     text,
    level       text NOT NULL,
    modes       text[] NOT NULL DEFAULT '{}',
    status      text NOT NULL DEFAULT 'active',
    geom        geometry(Polygon, 4326) NOT NULL,
    extra       jsonb NOT NULL DEFAULT '{}',
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE coverage IS 'Zones couvertes par les données (bandeau « données partielles » dans l''app).';
CREATE INDEX coverage_geom_idx ON coverage USING gist (geom);

CREATE TABLE alert (
    id              text PRIMARY KEY,
    position        int NOT NULL DEFAULT 0,
    effect          text NOT NULL,
    severity        text NOT NULL,
    status          text NOT NULL DEFAULT 'active',
    title_fr        text NOT NULL,
    title_ar        text,
    body_fr         text,
    body_ar         text,
    url             text,
    scope           jsonb NOT NULL,
    active_periods  jsonb NOT NULL,
    provenance      jsonb NOT NULL,
    extra           jsonb NOT NULL DEFAULT '{}',
    source_file     text,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE alert IS 'Perturbations (travaux, grève, ligne suspendue…), affichées dans l''app et appliquées aux horaires.';

-- ---------------------------------------------------------------------------------------------------------------
-- Publications : chaque génération du GTFS à partir de la base est tracée
-- ---------------------------------------------------------------------------------------------------------------

CREATE TABLE publication (
    uid           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_version  text,
    status        text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'ok', 'failed')),
    requested_by  text,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    errors        int,
    warnings      int,
    counts        jsonb,
    report        text
);
COMMENT ON TABLE publication IS 'Journal des publications (export de la base → validation → GTFS → OTP).';

-- Horodatage automatique des modifications
DO $$
DECLARE t text;
BEGIN
    FOR t IN SELECT table_name FROM information_schema.columns
             WHERE table_schema = 'public' AND column_name = 'updated_at'
               AND table_name NOT LIKE 'directus%'
    LOOP
        EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION thniya_touch()',
                       t || '_touch', t);
    END LOOP;
END $$;
