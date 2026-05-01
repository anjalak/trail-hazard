"use client";

import type { GeoJSONSource, LngLatLike, Map as MapboxMap } from "mapbox-gl";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { SectionCard } from "@/components/SectionCard";
import { StatusMessage } from "@/components/StatusMessage";
import { GeoJsonFeatureCollection, getTrailHazardsGeoJson } from "@/lib/graphql";
import { DEFAULT_EXPLORE_CENTER } from "@/lib/exploreDefaults";
import { Trail } from "@/types";

const DEFAULT_CENTER = DEFAULT_EXPLORE_CENTER;
const MAPBOX_PAUSED_BY_CONFIG = process.env.NEXT_PUBLIC_MAPBOX_SERVICE_PAUSED === "true";

type FeatureCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, GeoJSON.GeoJsonProperties>;

const WA_LNG_W = -130.5;
const WA_LNG_E = -115.8;
const WA_LAT_S = 41.5;
const WA_LAT_N = 52.5;

function inWashingtonBox(lng: number, lat: number): boolean {
  return lng >= WA_LNG_W && lng <= WA_LNG_E && lat >= WA_LAT_S && lat <= WA_LAT_N;
}

/** GeoJSON is always [lng, lat]; some sources swap them — correct when values clearly belong in the other axis. */
function normalizeLngLatPair(a: number, b: number): [number, number] | null {
  if (!Number.isFinite(a) || !Number.isFinite(b)) {
    return null;
  }
  if (inWashingtonBox(a, b)) {
    return [a, b];
  }
  if (inWashingtonBox(b, a)) {
    return [b, a];
  }
  if (Math.abs(a) <= 180 && Math.abs(b) <= 90) {
    return [a, b];
  }
  return null;
}

function trailPlotLngLat(trail: Trail): [number, number] | null {
  /** Nearby results only carry authoritative `lat`/`lng` from PostGIS; never plot `routeCoordinates` here. */
  if (trail.lng == null || trail.lat == null) {
    return null;
  }
  return normalizeLngLatPair(Number(trail.lng), Number(trail.lat));
}

function toTrailFeatures(trails: Trail[]): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: trails.flatMap((trail) => {
      const coordinates = trailPlotLngLat(trail);
      if (!coordinates) return [];
      return [
        {
          type: "Feature" as const,
          geometry: {
            type: "Point" as const,
            coordinates
          },
          properties: {
            id: trail.id,
            name: trail.name,
            region: trail.region,
            difficulty: trail.difficulty,
            length_km: trail.length_km
          }
        }
      ];
    })
  };
}

function emptyGeoJson(): GeoJsonFeatureCollection {
  return { type: "FeatureCollection", features: [] };
}

function isMapboxUsageLimitError(error: unknown): boolean {
  if (!error || typeof error !== "object") {
    return false;
  }

  const details = JSON.stringify(error).toLowerCase();
  return (
    details.includes("429") ||
    details.includes("too many requests") ||
    details.includes("rate limit") ||
    details.includes("quota")
  );
}

type ExploreMapProps = {
  trails: Trail[];
  trailsLoading: boolean;
  trailsError: string | null;
  /** Map + list share the same search pivot (from explore page). */
  pivotLngLat: [number, number];
  selectedLocation?: { center: [number, number]; label?: string } | null;
  /** When the map resolves browser geolocation (no manual city selected). */
  onBrowserPivot?: (center: [number, number]) => void;
  /** When true, skips the outer SectionCard (use when nested inside another card). */
  embedded?: boolean;
};

export function ExploreMap({
  trails,
  trailsLoading,
  trailsError,
  pivotLngLat,
  selectedLocation = null,
  onBrowserPivot,
  embedded = false
}: ExploreMapProps) {
  const router = useRouter();
  const token = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN;

  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const selectedLocationRef = useRef(selectedLocation);
  selectedLocationRef.current = selectedLocation;

  const [mapReady, setMapReady] = useState(false);
  const [selectedTrailId, setSelectedTrailId] = useState<number | null>(null);
  const [hazards, setHazards] = useState<GeoJsonFeatureCollection>(emptyGeoJson);
  const [mapboxPaused, setMapboxPaused] = useState<boolean>(MAPBOX_PAUSED_BY_CONFIG);
  const [locationStatus, setLocationStatus] = useState<string>(
    "Showing sample hikes in Washington until we have your location."
  );

  const trailById = useMemo(() => new globalThis.Map(trails.map((trail) => [trail.id, trail])), [trails]);
  const selectedTrail = selectedTrailId ? trailById.get(selectedTrailId) ?? null : null;
  const trailFeatures = useMemo(() => toTrailFeatures(trails), [trails]);

  const showLoadingOverlay = !mapReady || trailsLoading;

  useEffect(() => {
    if (!token || mapboxPaused || !containerRef.current || mapRef.current) {
      return;
    }

    let active = true;
    let map: MapboxMap | null = null;

    void import("mapbox-gl").then(({ default: mapboxgl }) => {
      if (!active || !containerRef.current || mapRef.current) {
        return;
      }

      mapboxgl.accessToken = token;
      map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/outdoors-v12",
        center: DEFAULT_CENTER as LngLatLike,
        zoom: 8,
        attributionControl: false,
        renderWorldCopies: false
      });
      const mapInstance = map;
      mapRef.current = mapInstance;

      mapInstance.addControl(new mapboxgl.NavigationControl({ visualizePitch: false }), "top-right");
      mapInstance.dragRotate.disable();
      mapInstance.touchZoomRotate.disableRotation();

      mapInstance.on("load", () => {
        /*
         * Avoid Mapbox clustering: cluster centroids can land on water between separated trailheads (e.g. Puget
         * Sound) or streak along arcs, looking like bogus “linear” placements. Nearby sets are modest in size.
         */
        mapInstance.addSource("trails", {
          type: "geojson",
          data: toTrailFeatures([]),
          cluster: false
        });

        mapInstance.addLayer({
          id: "trail-points",
          type: "circle",
          source: "trails",
          paint: {
            "circle-color": "#1e2e32",
            "circle-radius": 7,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2
          }
        });

        mapInstance.addLayer({
          id: "trail-selected",
          type: "circle",
          source: "trails",
          filter: ["==", ["get", "id"], -1],
          paint: {
            "circle-color": "#c6ee41",
            "circle-radius": 11,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2
          }
        });

        mapInstance.addSource("hazards", {
          type: "geojson",
          data: emptyGeoJson()
        });

        mapInstance.addLayer({
          id: "hazard-points",
          type: "circle",
          source: "hazards",
          paint: {
            "circle-color": [
              "match",
              ["get", "severity"],
              "high",
              "#dc2626",
              "medium",
              "#ea580c",
              "low",
              "#c6ee41",
              "#5a726f"
            ],
            "circle-radius": 6,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1
          }
        });

        mapInstance.on("click", "trail-points", (event) => {
          const feature = event.features?.[0];
          const idValue = feature?.properties?.id;
          const trailId = typeof idValue === "number" ? idValue : Number(idValue);
          if (!Number.isNaN(trailId)) {
            setSelectedTrailId(trailId);
          }
        });

        mapInstance.on("mouseenter", "trail-points", () => {
          mapInstance.getCanvas().style.cursor = "pointer";
        });
        mapInstance.on("mouseleave", "trail-points", () => {
          mapInstance.getCanvas().style.cursor = "";
        });

        mapInstance.on("error", (event) => {
          if (!active) return;
          if (isMapboxUsageLimitError(event.error)) {
            setMapboxPaused(true);
          }
        });
        setMapReady(true);
      });
    });

    return () => {
      active = false;
      setMapReady(false);
      map?.remove();
      mapRef.current = null;
    };
  }, [token, mapboxPaused]);

  useEffect(() => {
    setSelectedTrailId(null);
  }, [pivotLngLat[0], pivotLngLat[1]]);

  useEffect(() => {
    if (mapboxPaused) {
      return;
    }

    if (!onBrowserPivot) {
      return;
    }

    if (!navigator.geolocation) {
      setLocationStatus("Location is unavailable in this browser. Enter a ZIP code or city.");
      return;
    }

    setLocationStatus("Requesting your current location...");

    navigator.geolocation.getCurrentPosition(
      (position) => {
        if (selectedLocationRef.current?.center) {
          return;
        }

        const center: [number, number] = [position.coords.longitude, position.coords.latitude];
        onBrowserPivot(center);
        setLocationStatus("Using your current location for search.");
      },
      () => {
        setLocationStatus("Location access denied. Enter a ZIP code or city to explore trails.");
      },
      { timeout: 8000, maximumAge: 60000 }
    );
  }, [mapboxPaused, onBrowserPivot]);

  useEffect(() => {
    if (selectedLocation?.label) {
      setLocationStatus(`Showing trails near ${selectedLocation.label}.`);
      return;
    }
    if (selectedLocation?.center) {
      setLocationStatus("Showing trails near your selected location.");
    }
  }, [selectedLocation]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getSource("trails")) return;

    map.easeTo({ center: pivotLngLat as LngLatLike, duration: 500 });
  }, [pivotLngLat]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getSource("trails")) return;

    const source = map.getSource("trails") as GeoJSONSource;
    source.setData(trailFeatures);

    if (selectedTrailId != null) {
      map.setFilter("trail-selected", ["==", ["get", "id"], selectedTrailId]);
      const selectedFeature = trailFeatures.features.find(
        (feature) => Number(feature.properties?.id) === selectedTrailId
      ) as GeoJSON.Feature<GeoJSON.Point> | undefined;
      if (selectedFeature) {
        map.easeTo({ center: selectedFeature.geometry.coordinates as [number, number], duration: 500 });
      }
    } else {
      map.setFilter("trail-selected", ["==", ["get", "id"], -1]);
    }
  }, [trailFeatures, selectedTrailId]);

  useEffect(() => {
    let active = true;
    if (!selectedTrailId) {
      setHazards(emptyGeoJson());
      return;
    }

    getTrailHazardsGeoJson(selectedTrailId)
      .then((data) => {
        if (active) {
          setHazards(data);
        }
      })
      .catch(() => {
        if (active) {
          setHazards(emptyGeoJson());
        }
      });

    return () => {
      active = false;
    };
  }, [selectedTrailId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getSource("hazards")) return;
    const source = map.getSource("hazards") as GeoJSONSource;
    source.setData(hazards as unknown as FeatureCollection);
  }, [hazards]);

  if (!token) {
    const setupMessage = (
      <>
        <h2 id="map-explore-heading" className="text-2xl text-appText">
          Map explore
        </h2>
        <StatusMessage
          className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800"
          message="Add NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN to frontend/.env.local to enable the map."
          role="alert"
        />
      </>
    );
    return embedded ? <div className="space-y-3">{setupMessage}</div> : <SectionCard className="space-y-3" labelledBy="map-explore-heading">{setupMessage}</SectionCard>;
  }

  if (mapboxPaused) {
    const pausedMessage = (
      <>
        <h2 id="map-explore-heading" className="text-2xl text-appText">
          Map explore
        </h2>
        <StatusMessage
          className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800"
          message="Map service is currently paused to avoid Mapbox overage/rate-limit usage."
          role="alert"
        />
        <StatusMessage
          message="Set NEXT_PUBLIC_MAPBOX_SERVICE_PAUSED=false (or remove it) after usage resets."
          className="text-sm text-slate-600"
        />
      </>
    );
    return embedded ? <div className="space-y-3">{pausedMessage}</div> : <SectionCard className="space-y-3" labelledBy="map-explore-heading">{pausedMessage}</SectionCard>;
  }

  const mainMapContent = (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="map-explore-heading" className="text-2xl text-appText">
          Map explore
        </h2>
        <StatusMessage
          className="text-xs text-signal"
          message={showLoadingOverlay ? "Loading nearby trails..." : `${trails.length} trails loaded`}
          role="status"
          ariaLive="polite"
        />
      </div>

      <p id="map-explore-instructions" className="sr-only">
        Map showing trails near your location. Use the Nearby hikes list below for keyboard access to trails, or use map
        markers with a pointing device. Select a trail marker to choose it, then open the trail page with the button
        below the map.
      </p>

      <StatusMessage className="text-sm text-slate-600" message={locationStatus} role="status" ariaLive="polite" />

      {trailsError ? (
        <StatusMessage className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700" message={trailsError} role="alert" />
      ) : null}

      <div
        ref={containerRef}
        role="region"
        aria-label="Nearby trails map"
        aria-describedby="map-explore-instructions"
        className="h-[min(50vh,20rem)] w-full min-h-[220px] rounded-lg border border-borderSubtle sm:h-80 md:h-[32rem]"
      />

      {selectedTrail ? (
        <div className="flex flex-col gap-3 rounded-lg border border-borderSubtle bg-[#f2f6f5] p-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="font-medium text-appText">{selectedTrail.name}</p>
            <p className="text-sm text-[#364547]">
              {selectedTrail.region} - {selectedTrail.difficulty} - {selectedTrail.length_km} km
            </p>
            <p className="text-xs text-signal">
              Hazards on map: {hazards.features.length > 0 ? hazards.features.length : "none active"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => router.push(`/trails/${selectedTrail.id}`)}
            className="min-h-[44px] w-full shrink-0 rounded-md border border-accent bg-[#1f3033] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:border-accentSoft hover:bg-[#17282a] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 sm:w-auto sm:py-2"
          >
            Open trail
          </button>
        </div>
      ) : (
        <StatusMessage
          message="Select a trail marker on the map for details, then use Open trail. Keyboard users can use the Nearby hikes list below."
          className="text-sm text-[#5c6766]"
        />
      )}
    </>
  );

  return embedded ? (
    <div className="space-y-3">{mainMapContent}</div>
  ) : (
    <SectionCard className="space-y-3 md:p-6" labelledBy="map-explore-heading">
      {mainMapContent}
    </SectionCard>
  );
}
