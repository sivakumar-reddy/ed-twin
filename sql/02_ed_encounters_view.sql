-- =====================================================
-- ed-twin: ED Encounters Materialized View
-- Phase 1 wrap-up. Pre-joined analytical table for Phase 2.
-- =====================================================

DROP MATERIALIZED VIEW IF EXISTS ed_encounters CASCADE;

CREATE MATERIALIZED VIEW ed_encounters AS
WITH ed_visits AS (
    -- All emergency encounters
    SELECT
        e.id                      AS encounter_id,
        e.patient                 AS patient_id,
        e.organization            AS organization_id,
        e.provider                AS provider_id,
        e.start_time              AS arrival_time,
        e.stop_time               AS departure_time,
        e.code                    AS encounter_code,
        e.description             AS encounter_description,
        e.reason_code             AS chief_complaint_code,
        e.reason_description      AS chief_complaint,
        e.base_encounter_cost,
        e.total_claim_cost,
        e.payer_coverage
    FROM encounters e
    WHERE e.encounter_class = 'emergency'
),
admitted_after AS (
    -- For each ED visit, was there an inpatient encounter within 24h after?
    -- This is the "boarding" / "ED-to-admit" signal
    SELECT DISTINCT
        ed.encounter_id           AS ed_encounter_id,
        TRUE                      AS was_admitted
    FROM ed_visits ed
    JOIN encounters i
        ON i.patient = ed.patient_id
        AND i.encounter_class = 'inpatient'
        AND i.start_time >= ed.departure_time
        AND i.start_time <= ed.departure_time + INTERVAL '24 hours'
),
primary_diagnosis AS (
    -- The first (primary) diagnosis recorded during the ED encounter
    SELECT DISTINCT ON (encounter)
        encounter                 AS encounter_id,
        code                      AS primary_dx_code,
        description               AS primary_dx
    FROM conditions
    WHERE encounter IS NOT NULL
    ORDER BY encounter, start_date
)
SELECT
    -- IDs
    ed.encounter_id,
    ed.patient_id,
    ed.organization_id,
    ed.provider_id,

    -- Timing
    ed.arrival_time,
    ed.departure_time,
    EXTRACT(EPOCH FROM (ed.departure_time - ed.arrival_time)) / 60.0
                              AS los_minutes,
    EXTRACT(HOUR FROM ed.arrival_time)::INT
                              AS arrival_hour,
    EXTRACT(DOW  FROM ed.arrival_time)::INT
                              AS arrival_dow,
    TO_CHAR(ed.arrival_time, 'Day')
                              AS arrival_dow_name,

    -- Patient demographics
    p.gender,
    p.race,
    p.ethnicity,
    EXTRACT(YEAR FROM AGE(ed.arrival_time, p.birthdate))::INT
                              AS age_at_visit,

    -- Hospital
    o.name                    AS hospital_name,
    o.city                    AS hospital_city,

    -- Clinical
    ed.chief_complaint_code,
    ed.chief_complaint,
    dx.primary_dx_code,
    dx.primary_dx,

    -- Disposition flag (the headline column for boarding analysis)
    COALESCE(adm.was_admitted, FALSE)
                              AS admitted_to_inpatient,

    -- Cost
    ed.base_encounter_cost,
    ed.total_claim_cost,
    ed.payer_coverage

FROM ed_visits ed
JOIN patients p
    ON ed.patient_id = p.id
LEFT JOIN organizations o
    ON ed.organization_id = o.id
LEFT JOIN admitted_after adm
    ON ed.encounter_id = adm.ed_encounter_id
LEFT JOIN primary_diagnosis dx
    ON ed.encounter_id = dx.encounter_id
;

-- Indexes for the most common Phase 2 query patterns
CREATE INDEX idx_ed_arrival_time   ON ed_encounters(arrival_time);
CREATE INDEX idx_ed_hospital       ON ed_encounters(organization_id);
CREATE INDEX idx_ed_admitted       ON ed_encounters(admitted_to_inpatient);
CREATE INDEX idx_ed_arrival_hour   ON ed_encounters(arrival_hour);
CREATE INDEX idx_ed_age            ON ed_encounters(age_at_visit);

-- Verify
SELECT
    COUNT(*)                                          AS total_ed_visits,
    COUNT(*) FILTER (WHERE admitted_to_inpatient)     AS admitted,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE admitted_to_inpatient) / COUNT(*),
        2
    )                                                 AS admit_rate_pct,
    ROUND(AVG(los_minutes)::NUMERIC, 1)               AS mean_los_min,
    ROUND(MIN(los_minutes)::NUMERIC, 1)               AS min_los_min,
    ROUND(MAX(los_minutes)::NUMERIC, 1)               AS max_los_min
FROM ed_encounters;