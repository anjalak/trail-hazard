import { Trail, TrailConditions } from "@/types";

type TrailFilters = {
  stateCode?: string;
  city?: string;
  parkType?: string;
  parkNameContains?: string;
};

const endpoint = process.env.NEXT_PUBLIC_GRAPHQL_URL ?? "http://localhost:8000/graphql";

function _fetchHint(): string {
  if (typeof window !== "undefined" && window.location.origin.startsWith("https://")) {
    return ` From a browser this often means CORS: set FastAPI env CORS_ALLOW_ORIGINS=${window.location.origin}, (comma-separated for multiple previews).`;
  }
  return "";
}

async function executeGraphQL<T>(query: string, variables?: Record<string, unknown>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, variables }),
      cache: "no-store"
    });
  } catch {
    throw new Error(
      `Failed to reach GraphQL endpoint at ${endpoint}. Update NEXT_PUBLIC_GRAPHQL_URL (Vercel: Environment → Production Preview).${_fetchHint()}`
    );
  }

  if (!response.ok) {
    throw new Error(`GraphQL request failed: ${response.status}`);
  }

  const payload = (await response.json()) as { data?: T; errors?: { message: string }[] };
  if (payload.errors?.length) {
    throw new Error(payload.errors.map((err) => err.message).join(", "));
  }
  if (!payload.data) {
    throw new Error("GraphQL response did not include data.");
  }
  return payload.data;
}

export async function searchTrailsByName(query: string, filters?: TrailFilters): Promise<Trail[]> {
  const data = await executeGraphQL<{
    searchTrailsByName: Array<{
      id: number;
      name: string;
      region: string;
      lat?: number | null;
      lng?: number | null;
      difficulty: string;
      lengthKm: number;
      elevationGainM: number;
      traversabilityScore: number;
      location?: {
        stateCode: string;
        city?: string | null;
        parkName?: string | null;
        parkType?: string | null;
        county?: string | null;
      } | null;
    }>;
  }>(
    `query SearchTrailsByName(
      $query: String!
      $limit: Int!
      $stateCode: String
      $city: String
      $parkType: String
      $parkNameContains: String
    ) {
      searchTrailsByName(
        query: $query
        limit: $limit
        stateCode: $stateCode
        city: $city
        parkType: $parkType
        parkNameContains: $parkNameContains
      ) {
        id
        name
        region
        lat
        lng
        location {
          stateCode
          city
          parkName
          parkType
          county
        }
        difficulty
        lengthKm
        elevationGainM
        traversabilityScore
      }
    }`,
    {
      query,
      limit: 8,
      stateCode: filters?.stateCode,
      city: filters?.city,
      parkType: filters?.parkType,
      parkNameContains: filters?.parkNameContains
    }
  );
  return data.searchTrailsByName.map((trail) => ({
    id: trail.id,
    name: trail.name,
    region: trail.region,
    lat: trail.lat,
    lng: trail.lng,
    location: trail.location
      ? {
          state_code: trail.location.stateCode,
          city: trail.location.city,
          park_name: trail.location.parkName,
          park_type: trail.location.parkType,
          county: trail.location.county
        }
      : null,
    difficulty: trail.difficulty,
    length_km: trail.lengthKm,
    elevation_gain_m: trail.elevationGainM,
    traversability_score: trail.traversabilityScore
  }));
}

export async function getTrailConditions(trailId: number): Promise<TrailConditions | null> {
  const data = await executeGraphQL<{ trailConditions: TrailConditions | null }>(
    `query TrailConditions($trailId: Int!) {
      trailConditions(trailId: $trailId) {
        trailId
        name
        region
        lat
        lng
        location {
          stateCode
          city
          parkName
          parkType
          county
        }
        overallScore
        hazardSummary {
          activeCount
          highestSeverity
          types
        }
        activeHazards {
          id
          type
          severity
          source
          confidence
          reportedAt
          rawText
        }
        recentHazardCount
        hasRecentInfo
        recentReports {
          id
          conditionTags
          notes
          reporterName
          upvotes
        }
        weatherSnapshot {
          provider
          summary
          temperatureC
          windKph
          fetchedAt
          expiresAt
        }
      }
    }`,
    { trailId }
  );

  const raw = data.trailConditions as unknown as {
    trailId: number;
    region: string;
    lat?: number | null;
    lng?: number | null;
    location?: {
      stateCode: string;
      city?: string | null;
      parkName?: string | null;
      parkType?: string | null;
      county?: string | null;
    } | null;
    overallScore: number;
    hazardSummary: { activeCount: number; highestSeverity: "low" | "medium" | "high"; types: string[] };
    activeHazards: {
      id: number;
      type: string;
      severity: "low" | "medium" | "high";
      source: string;
      confidence: number;
      reportedAt: string;
      rawText?: string | null;
    }[];
    recentHazardCount: number;
    hasRecentInfo: boolean;
    recentReports: { id: number; conditionTags: string[]; notes?: string; reporterName?: string; upvotes: number }[];
    weatherSnapshot?: {
      provider: string;
      summary: string;
      temperatureC?: number | null;
      windKph?: number | null;
      fetchedAt: string;
      expiresAt: string;
    } | null;
    name: string;
  } | null;

  if (!raw) {
    return null;
  }

  return {
    trail_id: raw.trailId,
    name: raw.name,
    region: raw.region,
    lat: raw.lat,
    lng: raw.lng,
    location: raw.location
      ? {
          state_code: raw.location.stateCode,
          city: raw.location.city,
          park_name: raw.location.parkName,
          park_type: raw.location.parkType,
          county: raw.location.county
        }
      : null,
    overall_score: raw.overallScore,
    hazard_summary: {
      active_count: raw.hazardSummary.activeCount,
      highest_severity: raw.hazardSummary.highestSeverity,
      types: raw.hazardSummary.types
    },
    active_hazards: raw.activeHazards.map((hazard) => ({
      id: hazard.id,
      type: hazard.type,
      severity: hazard.severity,
      source: hazard.source,
      confidence: hazard.confidence,
      reported_at: hazard.reportedAt,
      raw_text: hazard.rawText
    })),
    recent_hazard_count: raw.recentHazardCount,
    has_recent_info: raw.hasRecentInfo,
    recent_reports: raw.recentReports.map((report) => ({
      id: report.id,
      condition_tags: report.conditionTags,
      notes: report.notes,
      reporter_name: report.reporterName,
      upvotes: report.upvotes
    })),
    weather_snapshot: raw.weatherSnapshot
      ? {
          provider: raw.weatherSnapshot.provider,
          summary: raw.weatherSnapshot.summary,
          temperature_c: raw.weatherSnapshot.temperatureC,
          wind_kph: raw.weatherSnapshot.windKph,
          fetched_at: raw.weatherSnapshot.fetchedAt,
          expires_at: raw.weatherSnapshot.expiresAt
        }
      : null
  };
}

export async function getNearbyTrails(lat: number, lng: number, km: number, filters?: TrailFilters): Promise<Trail[]> {
  const data = await executeGraphQL<{
    nearbyTrails: Array<{
      id: number;
      name: string;
      region: string;
      lat?: number | null;
      lng?: number | null;
      difficulty: string;
      lengthKm: number;
      elevationGainM: number;
      traversabilityScore: number;
      location?: {
        stateCode: string;
        city?: string | null;
        parkName?: string | null;
        parkType?: string | null;
        county?: string | null;
      } | null;
    }>;
  }>(
    `query NearbyTrails(
      $lat: Float!
      $lng: Float!
      $km: Float!
      $stateCode: String
      $city: String
      $parkType: String
      $parkNameContains: String
    ) {
      nearbyTrails(
        lat: $lat
        lng: $lng
        km: $km
        stateCode: $stateCode
        city: $city
        parkType: $parkType
        parkNameContains: $parkNameContains
      ) {
        id
        name
        region
        lat
        lng
        location {
          stateCode
          city
          parkName
          parkType
          county
        }
        difficulty
        lengthKm
        elevationGainM
        traversabilityScore
      }
    }`,
    {
      lat,
      lng,
      km,
      stateCode: filters?.stateCode,
      city: filters?.city,
      parkType: filters?.parkType,
      parkNameContains: filters?.parkNameContains
    }
  );
  return data.nearbyTrails.map((trail) => ({
    id: trail.id,
    name: trail.name,
    region: trail.region,
    lat: trail.lat,
    lng: trail.lng,
    location: trail.location
      ? {
          state_code: trail.location.stateCode,
          city: trail.location.city,
          park_name: trail.location.parkName,
          park_type: trail.location.parkType,
          county: trail.location.county
        }
      : null,
    difficulty: trail.difficulty,
    length_km: trail.lengthKm,
    elevation_gain_m: trail.elevationGainM,
    traversability_score: trail.traversabilityScore
  }));
}

export type GeoJsonFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: {
      type: "Point";
      coordinates: [number, number];
    };
    properties: Record<string, unknown>;
  }>;
};

export async function getTrailHazardsGeoJson(trailId: number): Promise<GeoJsonFeatureCollection> {
  const data = await executeGraphQL<{ trailHazardsGeojson: GeoJsonFeatureCollection }>(
    `query TrailHazardsGeoJson($trailId: Int!) {
      trailHazardsGeojson(trailId: $trailId)
    }`,
    { trailId }
  );
  return data.trailHazardsGeojson;
}
