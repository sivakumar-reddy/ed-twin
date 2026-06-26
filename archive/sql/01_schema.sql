-- =====================================================
-- ed-twin: Phase 1 Schema
-- Postgres schema for Synthea CSV ingest
-- Designed to be MIMIC-IV-ED compatible
-- =====================================================

-- Drop existing tables if rerunning
DROP TABLE IF EXISTS encounters CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS conditions CASCADE;
DROP TABLE IF EXISTS medications CASCADE;
DROP TABLE IF EXISTS procedures CASCADE;
DROP TABLE IF EXISTS observations CASCADE;
DROP TABLE IF EXISTS organizations CASCADE;
DROP TABLE IF EXISTS providers CASCADE;

-- =====================================================
-- PATIENTS
-- =====================================================
CREATE TABLE patients (
    id                  VARCHAR(50) PRIMARY KEY,
    birthdate           DATE,
    deathdate           DATE,
    ssn                 VARCHAR(20),
    drivers             VARCHAR(20),
    passport            VARCHAR(20),
    prefix              VARCHAR(10),
    first_name          VARCHAR(100),
    last_name           VARCHAR(100),
    suffix              VARCHAR(10),
    maiden              VARCHAR(100),
    marital             VARCHAR(5),
    race                VARCHAR(50),
    ethnicity           VARCHAR(50),
    gender              VARCHAR(5),
    birthplace          VARCHAR(200),
    address             VARCHAR(200),
    city                VARCHAR(100),
    state               VARCHAR(50),
    county              VARCHAR(100),
    zip                 VARCHAR(20),
    lat                 NUMERIC(10, 6),
    lon                 NUMERIC(10, 6),
    healthcare_expenses NUMERIC(12, 2),
    healthcare_coverage NUMERIC(12, 2),
    income              NUMERIC(12, 2)
);

CREATE INDEX idx_patients_gender ON patients(gender);
CREATE INDEX idx_patients_birthdate ON patients(birthdate);

-- =====================================================
-- ORGANIZATIONS (hospitals, clinics)
-- =====================================================
CREATE TABLE organizations (
    id            VARCHAR(50) PRIMARY KEY,
    name          VARCHAR(200),
    address       VARCHAR(200),
    city          VARCHAR(100),
    state         VARCHAR(50),
    zip           VARCHAR(20),
    lat           NUMERIC(10, 6),
    lon           NUMERIC(10, 6),
    phone         VARCHAR(50),
    revenue       NUMERIC(15, 2),
    utilization   INTEGER
);

-- =====================================================
-- PROVIDERS (individual clinicians)
-- =====================================================
CREATE TABLE providers (
    id              VARCHAR(50) PRIMARY KEY,
    organization    VARCHAR(50) REFERENCES organizations(id),
    name            VARCHAR(200),
    gender          VARCHAR(5),
    speciality      VARCHAR(100),
    address         VARCHAR(200),
    city            VARCHAR(100),
    state           VARCHAR(50),
    zip             VARCHAR(20),
    lat             NUMERIC(10, 6),
    lon             NUMERIC(10, 6),
    utilization     INTEGER
);

CREATE INDEX idx_providers_org ON providers(organization);

-- =====================================================
-- ENCOUNTERS (THE central table for ED-twin)
-- =====================================================
CREATE TABLE encounters (
    id                       VARCHAR(50) PRIMARY KEY,
    start_time               TIMESTAMP WITH TIME ZONE NOT NULL,
    stop_time                TIMESTAMP WITH TIME ZONE,
    patient                  VARCHAR(50) NOT NULL REFERENCES patients(id),
    organization             VARCHAR(50) REFERENCES organizations(id),
    provider                 VARCHAR(50) REFERENCES providers(id),
    payer                    VARCHAR(50),
    encounter_class          VARCHAR(50) NOT NULL,
    code                     BIGINT,
    description              VARCHAR(500),
    base_encounter_cost      NUMERIC(12, 2),
    total_claim_cost         NUMERIC(12, 2),
    payer_coverage           NUMERIC(12, 2),
    reason_code              BIGINT,
    reason_description       VARCHAR(500)
);

-- Critical indexes for ED analysis
CREATE INDEX idx_encounters_class ON encounters(encounter_class);
CREATE INDEX idx_encounters_patient ON encounters(patient);
CREATE INDEX idx_encounters_start ON encounters(start_time);
CREATE INDEX idx_encounters_org ON encounters(organization);
-- Composite index for the most common ED query pattern
CREATE INDEX idx_encounters_class_start ON encounters(encounter_class, start_time);

-- =====================================================
-- CONDITIONS (diagnoses)
-- =====================================================
CREATE TABLE conditions (
    start_date    DATE NOT NULL,
    stop_date     DATE,
    patient       VARCHAR(50) NOT NULL REFERENCES patients(id),
    encounter     VARCHAR(50) REFERENCES encounters(id),
    code          BIGINT,
    description   VARCHAR(500)
);

CREATE INDEX idx_conditions_patient ON conditions(patient);
CREATE INDEX idx_conditions_encounter ON conditions(encounter);
CREATE INDEX idx_conditions_code ON conditions(code);

-- =====================================================
-- MEDICATIONS
-- =====================================================
CREATE TABLE medications (
    start_time          TIMESTAMP WITH TIME ZONE NOT NULL,
    stop_time           TIMESTAMP WITH TIME ZONE,
    patient             VARCHAR(50) NOT NULL REFERENCES patients(id),
    payer               VARCHAR(50),
    encounter           VARCHAR(50) REFERENCES encounters(id),
    code                BIGINT,
    description         VARCHAR(500),
    base_cost           NUMERIC(12, 2),
    payer_coverage      NUMERIC(12, 2),
    dispenses           INTEGER,
    total_cost          NUMERIC(12, 2),
    reason_code         BIGINT,
    reason_description  VARCHAR(500)
);

CREATE INDEX idx_medications_patient ON medications(patient);
CREATE INDEX idx_medications_encounter ON medications(encounter);

-- =====================================================
-- PROCEDURES
-- =====================================================
CREATE TABLE procedures (
    start_time          TIMESTAMP WITH TIME ZONE NOT NULL,
    stop_time           TIMESTAMP WITH TIME ZONE,
    patient             VARCHAR(50) NOT NULL REFERENCES patients(id),
    encounter           VARCHAR(50) REFERENCES encounters(id),
    system              VARCHAR(50),
    code                VARCHAR(50),
    description         VARCHAR(500),
    base_cost           NUMERIC(12, 2),
    reason_code         BIGINT,
    reason_description  VARCHAR(500)
);

CREATE INDEX idx_procedures_patient ON procedures(patient);
CREATE INDEX idx_procedures_encounter ON procedures(encounter);

-- =====================================================
-- OBSERVATIONS (vitals + labs, the big table)
-- =====================================================
CREATE TABLE observations (
    date_time      TIMESTAMP WITH TIME ZONE NOT NULL,
    patient        VARCHAR(50) NOT NULL REFERENCES patients(id),
    encounter      VARCHAR(50) REFERENCES encounters(id),
    category       VARCHAR(100),
    code           VARCHAR(50),
    description    VARCHAR(500),
    value          VARCHAR(500),
    units          VARCHAR(50),
    type           VARCHAR(50)
);

CREATE INDEX idx_observations_patient ON observations(patient);
CREATE INDEX idx_observations_encounter ON observations(encounter);
CREATE INDEX idx_observations_code ON observations(code);
CREATE INDEX idx_observations_datetime ON observations(date_time);