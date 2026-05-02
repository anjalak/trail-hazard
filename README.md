# TrailIntel

**Trail intelligence for hikers** — search trails, see current-oriented conditions, and plan with recency-weighted hazard signals, community reports, and practical guidance in one place.

## Try it

**[Open the live app →](https://trail-hazard.vercel.app)** (Next.js on Vercel, talking to the GraphQL API on Render). Use search, trail detail, nearby discovery, and the map to explore how conditions are framed—not a substitute for official closures or what you see on the ground.

---

## The problem

Finding a hike and judging conditions usually means jumping between park pages, forums, and maps. Much of that information is stale or scattered. TrailIntel is a unified place to search trails, scan nearby options, and read **at-a-glance** danger context with actionable guidance.

---

## What you can do

- **Search** trails by name with optional location filters  
- **Open a trail** for a conditions card, hazard framing, and detail  
- **Discover** nearby hikes via geolocation or manual place entry  
- **Explore** a map with hazard overlays  
- **Contribute** community condition reports (rate-limited, moderated metadata)  

---

## How the data gets in

TrailIntel is built on **public land-manager sources**, not proprietary trail feeds.

- **Trail geometry & park context** — Imported from **National Park Service** public GIS (e.g. NPS Public Trails / FeatureServer) for the current MVP footprint (Washington national parks such as Mount Rainier, Olympic, North Cascades), stored in **PostGIS** with provenance on each route.
- **Hazards & bulletin-style signals** — Pulled from the **NPS Alerts API**, normalized and tagged (snow, washout, wildlife, etc.), then **recency-weighted** so newer signals matter more than stale ones in scoring and UI.
- **Weather snapshots** — **Open-Meteo** forecasts power on-trail weather context with explicit cache/freshness behavior.
- **Community** — User reports go through validation, moderation metadata, and Redis-backed rate limits before they affect the blend you see on a trail page.

A **Celery** worker/beat stack on **Render** (with **Redis**) runs scheduled ingestion and refresh jobs; **Supabase** holds the authoritative relational + geospatial data.

---

## Robotics & planning API

The same pipeline that powers the hiker UI also exposes a **robotics-oriented planning surface** over GraphQL—deliberately **not** a robot controller or SLAM stack, but a **pre-mission context layer** for outdoor routes:

- **PostGIS-backed route geometry**, hazard points, traversability priors, and confidence/recency metadata in one query shape.
- **`roboticsTraversability` / `roboticsArea`** — Route- and radius-level summaries for traversability and risk framing before you send hardware or a field team.
- **ROS-shaped payloads** — e.g. **`rosCompatibleRoute`**: pose-style samples along the polyline with aligned cost hints, so robotics tooling can consume the output without running ROS in the browser.
- **Optional ROS 2 bridge** (`ros_bridge.py`) — Polls GraphQL and publishes **`nav_msgs/Path`**, **`geometry_msgs/PoseArray`**, and risk/status topics for lab demos and integration smoke tests.

This allows for structured outdoor intelligence, machine-readable hazards, and honest scoping (planning aid, not autonomy).

---

## Tech stack

| Layer | Technologies |
|--------|----------------|
| **Frontend** | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Radix |
| **API** | FastAPI, Strawberry GraphQL |
| **Data** | Supabase (PostgreSQL + PostGIS) |
| **Cache & jobs** | Redis, Celery (worker + beat) |
| **Object storage** | Cloudflare R2 (photo uploads) |
| **Hosting** | Vercel (frontend), Render (API + workers), Supabase + Redis |

**Runtime:** Python **3.11+** for the backend and tooling. The repo includes [`.python-version`](.python-version) for pyenv/asdf.

---

## Architecture (short)

- **Frontend** — Server and client routes; GraphQL for search, trail pages, maps, and reports.  
- **Backend** — GraphQL resolvers, hazard scoring, conditions aggregation, `/health`.  
- **Database** — Supabase-hosted Postgres with PostGIS; optional in-memory fallback when the DB is unreachable (config-driven).  
- **Workers** — Ingestion, normalization, scoring, and refresh jobs.

**Typical flow:** search → trail page → API merges **NPS-sourced alerts**, **ingested hazards**, **weather**, **seasonal context**, and **community reports** into one conditions response.

```text
backend/    FastAPI, GraphQL, scoring, jobs, SQL schema & migrations
frontend/   Next.js app (routes, components, types)
```

---

## Project highlight

Geospatial SQL, public-sector ETL, recency-aware hazard scoring, GraphQL + optional ROS-shaped exports, background orchestration, accessible product UI, and end-to-end deployment (**Vercel · Render · Supabase**).

---

See [`CHANGELOG.md`](CHANGELOG.md) for a concise history of notable changes.
