-- Valeurs autorisées, identiques aux schémas JSON (data/schemas) : le back-office refuse une saisie invalide
-- avant même la validation de la publication.

ALTER TABLE place ADD CONSTRAINT place_kind_chk
    CHECK (kind IN ('station', 'platform', 'stop', 'louage_station', 'louage_bay', 'entrance', 'hail_point'));
ALTER TABLE place ADD CONSTRAINT place_wheelchair_chk CHECK (wheelchair IN ('yes', 'no', 'unknown'));
ALTER TABLE place ADD CONSTRAINT place_not_self_parent CHECK (parent_id IS NULL OR parent_id <> id);

ALTER TABLE calendar_event ADD CONSTRAINT calendar_event_kind_chk
    CHECK (kind IN ('holiday', 'period_event', 'special'));
ALTER TABLE calendar_event ADD CONSTRAINT calendar_event_status_chk CHECK (status IN ('estimated', 'confirmed'));

ALTER TABLE coverage ADD CONSTRAINT coverage_level_chk CHECK (level IN ('complete', 'partial'));

ALTER TABLE alert ADD CONSTRAINT alert_effect_chk
    CHECK (effect IN ('NO_SERVICE', 'REDUCED_SERVICE', 'DETOUR', 'STOP_CLOSED', 'DELAYS', 'INFO'));
ALTER TABLE alert ADD CONSTRAINT alert_severity_chk CHECK (severity IN ('info', 'warning', 'severe'));

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['mode', 'network', 'place', 'hub', 'line', 'coverage', 'alert']
    LOOP
        EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I CHECK (status IN (''draft'', ''active'', ''suspended'', ''archived''))',
                       t, t || '_status_chk');
    END LOOP;
    FOREACH t IN ARRAY ARRAY['network', 'place', 'line', 'fare', 'alert']
    LOOP
        EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I CHECK (provenance ? ''source'' AND provenance->>''source'' IN '
                       '(''OFFICIEL'', ''TERRAIN'', ''ESTIMATION'', ''SIGNALEMENT'', ''OSM'') AND provenance ? ''verified_at'')',
                       t, t || '_provenance_chk');
    END LOOP;
END $$;

-- Coordonnées plausibles (Tunisie et alentours) : une inversion lat/lon se voit tout de suite
ALTER TABLE place ADD CONSTRAINT place_in_tunisia
    CHECK (ST_X(geom) BETWEEN 7 AND 12 AND ST_Y(geom) BETWEEN 30 AND 38);

-- Vue de contrôle pour le back-office : arrêts sans ligne, lieux trop proches d'un homonyme…
CREATE VIEW place_usage AS
SELECT p.id, p.name_fr, p.kind, p.status,
       count(DISTINCT pt.line_id) AS lines,
       string_agg(DISTINCT pt.line_id, ', ' ORDER BY pt.line_id) AS line_ids
FROM place p
LEFT JOIN pattern_stop ps ON ps.place_id = p.id
LEFT JOIN pattern pt ON pt.uid = ps.pattern_uid
GROUP BY p.id, p.name_fr, p.kind, p.status;
COMMENT ON VIEW place_usage IS 'Lieux et nombre de lignes qui les desservent (0 = arrêt orphelin à vérifier).';
