CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS trail_locations (
  id SERIAL PRIMARY KEY,
  state_code TEXT NOT NULL,
  city TEXT,
  park_name TEXT,
  park_type TEXT CHECK (park_type IN ('national_park', 'state_park', 'national_forest', 'state_forest', 'other')),
  county TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (state_code, city, park_name, park_type)
);

CREATE INDEX IF NOT EXISTS idx_trail_locations_state_code ON trail_locations (state_code);
CREATE INDEX IF NOT EXISTS idx_trail_locations_state_code_lower ON trail_locations ((LOWER(state_code)));
CREATE INDEX IF NOT EXISTS idx_trail_locations_city_lower ON trail_locations ((LOWER(city)));
CREATE INDEX IF NOT EXISTS idx_trail_locations_park_name_lower ON trail_locations ((LOWER(park_name)));
CREATE INDEX IF NOT EXISTS idx_trail_locations_park_type_lower ON trail_locations ((LOWER(park_type)));

CREATE TABLE IF NOT EXISTS trails (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  region TEXT NOT NULL,
  location_id INT REFERENCES trail_locations(id) ON DELETE SET NULL,
  difficulty TEXT NOT NULL,
  length_km NUMERIC(6,2) NOT NULL,
  elevation_gain_m INT NOT NULL,
  geom GEOMETRY(LineString, 4326),
  source_url TEXT,
  geometry_quality TEXT NOT NULL DEFAULT 'synthetic'
    CHECK (geometry_quality IN ('synthetic', 'curated', 'imported_usgs', 'imported_nps', 'imported_osm', 'unknown')),
  geometry_source TEXT NOT NULL DEFAULT 'seed.sql',
  geometry_source_url TEXT,
  data_quality_status TEXT NOT NULL DEFAULT 'demo_synthetic'
    CHECK (data_quality_status IN ('verified', 'demo_synthetic')),
  validation_source TEXT,
  validated_at TIMESTAMPTZ,
  validation_notes TEXT,
  traversability_score NUMERIC(4,3) DEFAULT 0.0,
  last_scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trails_geom ON trails USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_trails_name_lower ON trails ((LOWER(name)));
CREATE INDEX IF NOT EXISTS idx_trails_location_id ON trails (location_id);

ALTER TABLE trails
  ADD COLUMN IF NOT EXISTS geometry_quality TEXT NOT NULL DEFAULT 'synthetic',
  ADD COLUMN IF NOT EXISTS geometry_source TEXT NOT NULL DEFAULT 'seed.sql',
  ADD COLUMN IF NOT EXISTS geometry_source_url TEXT,
  ADD COLUMN IF NOT EXISTS data_quality_status TEXT NOT NULL DEFAULT 'demo_synthetic',
  ADD COLUMN IF NOT EXISTS validation_source TEXT,
  ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS validation_notes TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'trails_geometry_quality_check'
  ) THEN
    ALTER TABLE trails
      ADD CONSTRAINT trails_geometry_quality_check
      CHECK (geometry_quality IN ('synthetic', 'curated', 'imported_usgs', 'imported_nps', 'imported_osm', 'unknown'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'trails_data_quality_status_check'
  ) THEN
    ALTER TABLE trails
      ADD CONSTRAINT trails_data_quality_status_check
      CHECK (data_quality_status IN ('verified', 'demo_synthetic'));
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS hazards (
  id SERIAL PRIMARY KEY,
  trail_id INT NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
  location GEOMETRY(Point, 4326),
  source TEXT NOT NULL CHECK (source IN ('user', 'scraped', 'cv_pipeline')),
  confidence NUMERIC(3,2) NOT NULL DEFAULT 0.75,
  reported_at TIMESTAMPTZ NOT NULL,
  resolved_at TIMESTAMPTZ,
  raw_text TEXT
);

CREATE INDEX IF NOT EXISTS idx_hazards_trail_id ON hazards (trail_id);
CREATE INDEX IF NOT EXISTS idx_hazards_active ON hazards (trail_id, resolved_at, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_hazards_location ON hazards USING GIST (location);

CREATE TABLE IF NOT EXISTS user_reports (
  id SERIAL PRIMARY KEY,
  trail_id INT NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
  location GEOMETRY(Point, 4326),
  photo_url TEXT,
  condition_tags TEXT[] NOT NULL DEFAULT '{}',
  notes TEXT,
  reporter_name TEXT,
  reported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  upvotes INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_user_reports_trail_id ON user_reports (trail_id, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_reports_location ON user_reports USING GIST (location);

CREATE TABLE IF NOT EXISTS seasonal_intel (
  id SERIAL PRIMARY KEY,
  trail_id INT NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
  month INT NOT NULL CHECK (month BETWEEN 1 AND 12),
  wildlife_alerts JSONB NOT NULL DEFAULT '[]'::jsonb,
  plant_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  gear_recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
  avg_temp_c NUMERIC(5,2),
  avg_snowpack_cm NUMERIC(6,2),
  source TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (trail_id, month)
);

CREATE TABLE IF NOT EXISTS reviews (
  id SERIAL PRIMARY KEY,
  trail_id INT NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
  source_platform TEXT NOT NULL,
  external_review_id TEXT,
  source_url TEXT,
  rating NUMERIC(3,2),
  text TEXT,
  sentiment_score NUMERIC(4,3),
  scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  author_handle TEXT
);

ALTER TABLE reviews
  ADD COLUMN IF NOT EXISTS external_review_id TEXT,
  ADD COLUMN IF NOT EXISTS source_url TEXT;

CREATE INDEX IF NOT EXISTS idx_reviews_trail_id ON reviews (trail_id, scraped_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviews_source_external_id_unique
ON reviews (source_platform, external_review_id)
WHERE external_review_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS weather_cache (
  id SERIAL PRIMARY KEY,
  trail_id INT NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  summary TEXT,
  temperature_c NUMERIC(5,2),
  wind_kph NUMERIC(5,2),
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_cache_trail_provider_unique
ON weather_cache (trail_id, provider);

CREATE TABLE IF NOT EXISTS source_fetch_log (
  id BIGSERIAL PRIMARY KEY,
  source_name TEXT NOT NULL,
  fetch_scope TEXT NOT NULL,
  period_start DATE,
  period_end DATE,
  content_hash TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_source_fetch_log_uniqueness
ON source_fetch_log (source_name, fetch_scope, period_start, period_end, content_hash);

-- Ingestion task dead-letter (terminal Celery failure after max retries)
CREATE TABLE IF NOT EXISTS ingestion_task_failures (
  id BIGSERIAL PRIMARY KEY,
  task_name TEXT NOT NULL,
  task_id TEXT,
  task_args JSONB NOT NULL DEFAULT '[]',
  task_kwargs JSONB NOT NULL DEFAULT '{}',
  exc_type TEXT NOT NULL,
  exc_message TEXT,
  exc_repr TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_task_failures_created_at ON ingestion_task_failures (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingestion_task_failures_task_name ON ingestion_task_failures (task_name);
