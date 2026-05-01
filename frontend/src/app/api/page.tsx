import type { Metadata } from "next";

import { AppLinkButton } from "@/components/AppLinkButton";
import { CopyCodeBlock } from "@/components/CopyCodeBlock";
import { SectionCard } from "@/components/SectionCard";

const graphQLEndpoint = process.env.NEXT_PUBLIC_GRAPHQL_URL ?? "http://localhost:8000/graphql";

export const metadata: Metadata = {
  title: "API — TrailIntel",
  description:
    "TrailIntel GraphQL endpoint, core operations, robotics traversability payloads, and integration notes for developers."
};

const tocLinks = [
  { href: "#operations", label: "Operations" },
  { href: "#quick-start", label: "Quick start" },
  { href: "#responses", label: "Responses & errors" },
  { href: "#hiker-example", label: "Trail & conditions" },
  { href: "#robotics-queries", label: "Robotics queries" },
  { href: "#area-screening", label: "Area screening" },
  { href: "#ros-format", label: "ROS-compatible route" },
  { href: "#quality-fields", label: "Quality fields" },
  { href: "#reading-payload", label: "Reading the payload" },
  { href: "#client-fetch", label: "Client fetch" }
] as const;

const graphqlOperations = [
  {
    name: "searchTrailsByName",
    kind: "Query",
    summary: "Text search with optional location filters (state, city, park type, park name)."
  },
  { name: "trail", kind: "Query", summary: "Single trail by numeric id, including location when available." },
  {
    name: "nearbyTrails",
    kind: "Query",
    summary: "Trails near a point within a radius (km), with the same optional filters as search."
  },
  { name: "trailConditions", kind: "Query", summary: "Conditions bundle: hazards, weather snapshot, seasonal intel, reports." },
  { name: "trailHazards", kind: "Query", summary: "Active or all hazards for a trail." },
  { name: "trailHazardsGeojson", kind: "Query", summary: "Hazard features as GeoJSON for map overlays." },
  { name: "trailReviews", kind: "Query", summary: "Recent reviews for a trail." },
  {
    name: "roboticsTraversability",
    kind: "Query",
    summary: "Pre-mission robotics payload: scores, route GeoJSON, ROS-shaped route, costs, planning notes."
  },
  {
    name: "roboticsArea",
    kind: "Query",
    summary: "Radius-based area summary: trail candidates, risk density, recommended trail ids."
  },
  { name: "submitReport", kind: "Mutation", summary: "Submit a trail condition report (rate limits may apply)." },
  { name: "upvoteReport", kind: "Mutation", summary: "Upvote a community report." },
  { name: "resolveReport", kind: "Mutation", summary: "Mark a report resolved (moderation / internal use)." }
];

const roboticsQuery = `query RoboticsTraversability($trailId: Int!) {
  roboticsTraversability(trailId: $trailId) {
    trailId
    name
    traversabilityScore
    riskScore
    effortScore
    geometryQuality
    geometrySource
    vertexCount
    hazardLocationQuality
    routeGeojson
    hazardsGeojson
    hazardSummary {
      activeCount
      highestSeverity
      types
    }
    dataFreshness {
      generatedAt
      latestHazardAt
      sourceCount
      stale
    }
    rosCompatibleRoute
    segmentCosts
    elevationProfile
    costModel
    planningNotes
  }
}`;

const roboticsAreaQuery = `query RoboticsArea($lat: Float!, $lng: Float!, $radiusM: Float!) {
  roboticsArea(lat: $lat, lng: $lng, radiusM: $radiusM) {
    center {
      lat
      lng
    }
    radiusM
    activeHazardCount
    hazardDensity
    areaRiskScore
    highestRiskTrail {
      trailId
      name
      riskScore
      activeHazardCount
      hazardLocationQuality
    }
    recommendedTrailIds
    trails {
      trailId
      name
      traversabilityScore
      riskScore
      effortScore
      activeHazardCount
      hazardLocationQuality
    }
    generatedAt
  }
}`;

const hikerQueryExample = `query TrailOverview($trailId: Int!) {
  trail(id: $trailId) {
    id
    name
    region
    lengthKm
    elevationGainM
  }
  trailConditions(trailId: $trailId) {
    overallScore
    hazardSummary {
      activeCount
      highestSeverity
      types
    }
    weatherSnapshot {
      summary
      temperatureC
    }
  }
}`;

const responseExcerpt = `{
  "roboticsTraversability": {
    "trailId": 1,
    "name": "Snow Lake Trail",
    "geometryQuality": "synthetic",
    "geometrySource": "seed.sql",
    "vertexCount": 2,
    "hazardLocationQuality": "trail_level",
    "hazardsGeojson": {
      "type": "FeatureCollection",
      "features": []
    },
    "dataFreshness": {
      "generatedAt": "2026-04-29T06:00:00Z",
      "latestHazardAt": "2026-04-28T12:00:00Z",
      "sourceCount": 2,
      "stale": false
    },
    "rosCompatibleRoute": {
      "header": {
        "frame_id": "map",
        "generated_at": "2026-04-29T06:00:00Z",
        "coordinate_system": "WGS84",
        "axes": {
          "x": "longitude_degrees",
          "y": "latitude_degrees",
          "z": "elevation_meters"
        }
      },
      "poses": [
        {
          "position": {
            "x": -121.52,
            "y": 47.445,
            "z": 0.0
          },
          "orientation": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "w": 1.0
          }
        }
      ],
      "costs": [0.31]
    },
    "segmentCosts": [
      {
        "index": 0,
        "estimated_gain_m": 38.4,
        "estimated_grade": 0.1412,
        "hazard_component": 0.31,
        "cost": 0.27
      },
      {
        "index": 1,
        "estimated_gain_m": 55.7,
        "estimated_grade": 0.2038,
        "hazard_component": 0.31,
        "cost": 0.33
      }
    ],
    "elevationProfile": [
      { "index": 0, "distance_ratio": 0.0, "elevation_m": 0.0 },
      { "index": 1, "distance_ratio": 0.091, "elevation_m": 38.4 },
      { "index": 2, "distance_ratio": 0.182, "elevation_m": 94.1 }
    ],
    "costModel": {
      "version": "v2-segment-aware",
      "fallback_mode": true,
      "weights": {
        "traversability": 0.35,
        "hazard": 0.4,
        "segment_effort": 0.25
      }
    },
    "planningNotes": [
      "ROS-compatible message format generated from route geometry for pre-mission planning.",
      "Route pose coordinates are geographic (WGS84 lon/lat), not local ENU map meters.",
      "Active hazards are treated as route-level risk because exact hazard GPS points are not available."
    ]
  }
}`;

const areaResponseExcerpt = `{
  "roboticsArea": {
    "center": {
      "lat": 47.414,
      "lng": -121.428
    },
    "radiusM": 40000,
    "activeHazardCount": 3,
    "hazardDensity": 0.597,
    "areaRiskScore": 0.347,
    "highestRiskTrail": {
      "trailId": 3,
      "name": "Mailbox Peak Trail",
      "riskScore": 0.52,
      "activeHazardCount": 1,
      "hazardLocationQuality": "trail_level"
    },
    "recommendedTrailIds": [2, 1],
    "trails": [
      {
        "trailId": 2,
        "name": "Rattlesnake Ledge",
        "traversabilityScore": 0.78,
        "riskScore": 0.26,
        "effortScore": 0.31,
        "activeHazardCount": 0,
        "hazardLocationQuality": "unknown"
      },
      {
        "trailId": 1,
        "name": "Snow Lake Trail",
        "traversabilityScore": 0.72,
        "riskScore": 0.31,
        "effortScore": 0.41,
        "activeHazardCount": 2,
        "hazardLocationQuality": "trail_level"
      }
    ],
    "generatedAt": "2026-04-29T06:00:00Z"
  }
}`;

const curlTraversability = `curl -s -X POST ${graphQLEndpoint} \\
  -H "Content-Type: application/json" \\
  -d '{"query":"query($trailId:Int!){ roboticsTraversability(trailId:$trailId){ trailId name riskScore traversabilityScore effortScore hazardLocationQuality geometryQuality geometrySource vertexCount planningNotes rosCompatibleRoute segmentCosts elevationProfile costModel hazardSummary { activeCount highestSeverity types } dataFreshness { generatedAt latestHazardAt sourceCount stale } }}","variables":{"trailId":1}}'`;

const curlArea = `curl -s -X POST ${graphQLEndpoint} \\
  -H "Content-Type: application/json" \\
  -d '{"query":"query($lat:Float!,$lng:Float!,$radiusM:Float!){ roboticsArea(lat:$lat,lng:$lng,radiusM:$radiusM){ center { lat lng } radiusM activeHazardCount hazardDensity areaRiskScore highestRiskTrail { trailId name riskScore } recommendedTrailIds trails { trailId name riskScore traversabilityScore effortScore activeHazardCount hazardLocationQuality } generatedAt }}","variables":{"lat":47.414,"lng":-121.428,"radiusM":40000}}'`;

const curlTrailOverview = `curl -s -X POST ${graphQLEndpoint} \\
  -H "Content-Type: application/json" \\
  -d '{"query":"query($trailId:Int!){ trail(id:$trailId){ id name region lengthKm elevationGainM } trailConditions(trailId:$trailId){ overallScore hazardSummary{ activeCount highestSeverity types } weatherSnapshot{ summary temperatureC } } }","variables":{"trailId":1}}'`;

const fetchSnippet = `const response = await fetch("${graphQLEndpoint}", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: \`query($trailId:Int!){
      roboticsTraversability(trailId:$trailId){
        trailId
        name
        riskScore
        rosCompatibleRoute
        planningNotes
      }
    }\`,
    variables: { trailId: 1 }
  })
});

const payload = await response.json();
console.log(payload.data.roboticsTraversability);`;

const metadataFields = [
  {
    name: "geometryQuality",
    description:
      "Describes the route geometry provenance level, such as synthetic demo data, curated project data, or a future imported GIS source."
  },
  {
    name: "geometrySource",
    description:
      "Names the source label or URL behind the route geometry. Current seeded routes are simplified and should not be treated as survey-grade."
  },
  {
    name: "vertexCount",
    description:
      "Counts original route vertices before interpolation. A two-vertex route may still produce more poses in the ROS-compatible message format."
  },
  {
    name: "hazardLocationQuality",
    description:
      "Explains whether hazards have exact point coordinates. Current MVP hazards are often trail-level risk unless a hazard row has a real location."
  },
  {
    name: "rosCompatibleRoute.header.coordinate_system",
    description:
      "Identifies the route coordinate reference. Current route poses use WGS84 lon/lat values in x/y and should be transformed before local planner execution."
  },
  {
    name: "effortScore / segmentCosts / elevationProfile",
    description:
      "These fields expose effort and per-segment cost context. Costs are segment-aware when geometry/elevation detail exists, and marked as fallback mode when source detail is limited."
  }
];

export default function ApiPage() {
  return (
    <div className="space-y-5">
      <SectionCard className="space-y-4 scroll-mt-6">
        <header className="space-y-3">
          <p className="text-xs uppercase tracking-[0.22em] text-signal">Developer API</p>
          <h1 className="max-w-3xl text-4xl font-extrabold text-appText sm:text-5xl">
            Trail intelligence for hikers and planning tools.
          </h1>
          <p className="max-w-3xl text-sm text-[#3c4a4b] sm:text-base">
            TrailIntel turns hazards and conditions into human-readable hiking guidance for the website. Developers and
            robotics engineers can use the GraphQL API to retrieve the same route, traversability, and hazard signals as
            structured planning payloads.
          </p>
        </header>
        <div className="flex flex-col gap-2 sm:flex-row">
          <AppLinkButton href="/" variant="outline" className="w-full sm:w-auto">
            Back to search
          </AppLinkButton>
          <AppLinkButton href="/explore" variant="outline" className="w-full sm:w-auto">
            Explore trails
          </AppLinkButton>
        </div>
        <nav aria-label="On this page" className="rounded-lg border border-borderSubtle bg-surfaceMuted/80 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-signal">On this page</p>
          <ul className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            {tocLinks.map((item) => (
              <li key={item.href}>
                <a
                  href={item.href}
                  className="text-[#263638] underline decoration-borderSubtle underline-offset-4 hover:text-accent hover:decoration-accent"
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </SectionCard>

      <SectionCard id="operations" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">GraphQL operations</h2>
        <p className="text-sm text-[#263638]">
          Field names use GraphQL camelCase (for example <code className="text-appText">trailHazardsGeojson</code>). The
          backend is Strawberry on FastAPI; you can open{" "}
          <a
            className="font-medium text-accent underline decoration-accent/50 underline-offset-2 hover:decoration-accent"
            href={graphQLEndpoint}
            target="_blank"
            rel="noopener noreferrer"
          >
            the GraphQL URL
          </a>{" "}
          in a browser while the server is running to use GraphiQL and explore the live schema.
        </p>
        <div className="overflow-x-auto rounded-lg border border-borderSubtle">
          <table className="w-full min-w-[32rem] border-collapse text-left text-sm text-[#263638]">
            <thead>
              <tr className="border-b border-borderSubtle bg-surfaceMuted">
                <th scope="col" className="px-3 py-2 font-semibold text-appText">
                  Name
                </th>
                <th scope="col" className="px-3 py-2 font-semibold text-appText">
                  Type
                </th>
                <th scope="col" className="px-3 py-2 font-semibold text-appText">
                  Purpose
                </th>
              </tr>
            </thead>
            <tbody>
              {graphqlOperations.map((op) => (
                <tr key={op.name} className="border-b border-borderSubtle/80 last:border-0">
                  <td className="px-3 py-2.5 font-mono text-xs text-appText">{op.name}</td>
                  <td className="px-3 py-2.5 text-xs">{op.kind}</td>
                  <td className="px-3 py-2.5">{op.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard id="quick-start" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">Endpoint and quick start</h2>
        <p className="text-sm text-[#263638]">
          Send <code className="text-appText">POST</code> requests with a JSON body <code className="text-appText">{`{ "query", "variables" }`}</code>{" "}
          to <code className="break-all text-appText">{graphQLEndpoint}</code>. The web app uses the same URL via{" "}
          <code className="text-appText">NEXT_PUBLIC_GRAPHQL_URL</code> (defaults to local development if unset).
        </p>
        <p className="text-sm text-[#263638]">
          Use <code className="text-appText">roboticsTraversability</code> for one trail mission payload and{" "}
          <code className="text-appText">roboticsArea</code> for radius-level mission screening.
        </p>
        <CopyCodeBlock code={curlTraversability} copyLabel="Copy curl (robotics)" />
        <CopyCodeBlock code={curlArea} copyLabel="Copy curl (area)" />
      </SectionCard>

      <SectionCard id="responses" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">Responses and errors</h2>
        <p className="text-sm text-[#263638]">
          Successful calls return JSON with a <code className="text-appText">data</code> key. GraphQL errors appear in an{" "}
          <code className="text-appText">errors</code> array (validation, resolver failures, rate limits on mutations).
          Always check <code className="text-appText">errors</code> before assuming <code className="text-appText">data</code> is complete.
        </p>
        <pre className="overflow-x-auto rounded-lg border border-borderSubtle bg-[#142224] p-4 text-xs text-[#f4ede3]">
          <code>{`{
  "data": { "trail": { "id": 1, "name": "…" } },
  "errors": [{ "message": "…" }]
}`}</code>
        </pre>
        <p className="text-sm text-[#263638]">
          Call the API from the same origin as this site, or from tools like curl, without extra headers beyond{" "}
          <code className="text-appText">Content-Type: application/json</code>. If you embed the endpoint in another web
          origin, ensure the backend CORS settings allow that origin.
        </p>
      </SectionCard>

      <SectionCard className="space-y-3">
        <h2 className="text-2xl text-appText">What the API provides</h2>
        <p className="text-sm text-[#263638]">
          The public GraphQL surface exposes trail search, nearby trail discovery, trail conditions, active hazards,
          reviews, and robotics-facing traversability payloads. The robotics payload is intended for pre-mission
          context: route geometry, route-level costs, traversability scores, and planning notes.
        </p>
        <p className="text-sm text-[#263638]">
          It is not robot control, autonomous navigation, SLAM, or real-time obstacle avoidance.
        </p>
      </SectionCard>

      <SectionCard id="hiker-example" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">Trail overview (hiker / product)</h2>
        <p className="text-sm text-[#263638]">
          This is the same shape the frontend uses for trail detail: core trail facts plus the conditions card payload.
        </p>
        <CopyCodeBlock code={hikerQueryExample} copyLabel="Copy GraphQL query" />
        <CopyCodeBlock code={curlTrailOverview} copyLabel="Copy curl" />
      </SectionCard>

      <SectionCard id="robotics-queries" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">Robotics traversability query</h2>
        <p className="text-sm text-[#263638]">
          Call the backend GraphQL endpoint with a trail id to retrieve a robotics planning payload.
        </p>
        <CopyCodeBlock code={roboticsQuery} copyLabel="Copy full query" />
      </SectionCard>

      <SectionCard id="area-screening" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">Area screening query</h2>
        <p className="text-sm text-[#263638]">
          Use this query to compare nearby trails, inspect area risk density, and pick lower-risk candidate trail ids.
        </p>
        <CopyCodeBlock code={roboticsAreaQuery} copyLabel="Copy full query" />
        <p className="text-sm text-[#263638]">Example <code className="text-appText">data</code> excerpt:</p>
        <CopyCodeBlock code={areaResponseExcerpt} copyLabel="Copy JSON excerpt" />
      </SectionCard>

      <SectionCard id="ros-format" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">ROS-compatible message format</h2>
        <p className="text-sm text-[#263638]">
          <code className="text-appText">rosCompatibleRoute</code> is JSON shaped like a ROS route message, with{" "}
          <code className="text-appText">header.frame_id</code>, route <code className="text-appText">poses</code>, and
          per-pose <code className="text-appText">costs</code>. It does not require a ROS runtime.
        </p>
        <CopyCodeBlock code={responseExcerpt} copyLabel="Copy JSON excerpt" />
      </SectionCard>

      <SectionCard id="quality-fields" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">Quality and provenance fields</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {metadataFields.map((field) => (
            <article key={field.name} className="rounded-lg border border-borderSubtle bg-surfaceMuted p-3">
              <h3 className="font-mono text-sm text-appText">{field.name}</h3>
              <p className="mt-1 text-sm text-[#263638]">{field.description}</p>
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard id="reading-payload" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">How to read the robotics payload</h2>
        <p className="text-sm text-[#263638]">
          Treat hazards as route-level risk unless <code className="text-appText">hazardLocationQuality</code> is{" "}
          <code className="text-appText">exact</code>. Current seeded route geometry is simplified demo geometry, so
          clients should use <code className="text-appText">geometryQuality</code>,{" "}
          <code className="text-appText">geometrySource</code>, and <code className="text-appText">vertexCount</code> when
          deciding whether a route is suitable for a downstream planner. <code className="text-appText">rosCompatibleRoute</code>{" "}
          points are currently lon/lat in WGS84, so transform coordinates into your robot map frame before execution.{" "}
          <code className="text-appText">hazardsGeojson</code> only includes exact point features when a hazard row has
          real coordinates.
        </p>
      </SectionCard>

      <SectionCard id="client-fetch" className="scroll-mt-6 space-y-3">
        <h2 className="text-2xl text-appText">Client fetch example</h2>
        <p className="text-sm text-[#263638]">
          This fetch pattern matches the backend GraphQL contract and can be used by mission-planning tooling. Replace the
          URL with your deployed <code className="text-appText">NEXT_PUBLIC_GRAPHQL_URL</code> when not running locally.
        </p>
        <CopyCodeBlock code={fetchSnippet} copyLabel="Copy JavaScript" />
      </SectionCard>
    </div>
  );
}
