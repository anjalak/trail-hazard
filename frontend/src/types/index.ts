export type TrailLocation = {
  state_code: string;
  city?: string | null;
  park_name?: string | null;
  park_type?: string | null;
  county?: string | null;
};

export type Trail = {
  id: number;
  name: string;
  region: string;
  location?: TrailLocation | null;
  lat?: number | null;
  lng?: number | null;
  /** GeoJSON LineString [[lng, lat], …] when API has geometry; explore map prefers `lat`/`lng` for pins. */
  route_coordinates?: number[][] | null;
  difficulty: string;
  length_km: number;
  elevation_gain_m: number;
  traversability_score: number;
};

export type TrailConditions = {
  trail_id: number;
  name: string;
  region: string;
  location?: TrailLocation | null;
  lat?: number | null;
  lng?: number | null;
  overall_score: number;
  hazard_summary: {
    active_count: number;
    highest_severity: "low" | "medium" | "high";
    types: string[];
  };
  active_hazards: {
    id: number;
    type: string;
    severity: "low" | "medium" | "high";
    source: string;
    confidence: number;
    reported_at: string;
    raw_text?: string | null;
  }[];
  recent_hazard_count: number;
  has_recent_info: boolean;
  recent_reports: {
    id: number;
    condition_tags: string[];
    notes?: string | null;
    reporter_name?: string | null;
    upvotes: number;
  }[];
  weather_snapshot?: {
    provider: string;
    summary: string;
    temperature_c?: number | null;
    wind_kph?: number | null;
    fetched_at: string;
    expires_at: string;
  } | null;
};
