"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AppLinkButton } from "@/components/AppLinkButton";
import { ExploreMap } from "@/components/ExploreMap";
import { NearbyTrails } from "@/components/NearbyTrails";
import { SectionCard } from "@/components/SectionCard";
import {
  DEFAULT_EXPLORE_CENTER,
  DEFAULT_EXPLORE_RADIUS_KM,
  USER_NEARBY_RADIUS_KM
} from "@/lib/exploreDefaults";
import { getNearbyTrails } from "@/lib/graphql";
import { Trail } from "@/types";

type SelectedLocation = {
  center: [number, number];
  label?: string;
};

export default function ExplorePage() {
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);
  const [browserPivot, setBrowserPivot] = useState<[number, number] | null>(null);

  const pivotLngLat = useMemo((): [number, number] => {
    const c = selectedLocation?.center;
    if (c?.length === 2) {
      return c;
    }
    if (browserPivot) {
      return browserPivot;
    }
    return DEFAULT_EXPLORE_CENTER;
  }, [selectedLocation, browserPivot]);

  const autoRadiusKm = useMemo(
    () =>
      selectedLocation?.center && selectedLocation.center.length === 2
        ? USER_NEARBY_RADIUS_KM
        : DEFAULT_EXPLORE_RADIUS_KM,
    [selectedLocation]
  );

  const [radiusKmOverride, setRadiusKmOverride] = useState<number | null>(null);
  const trailFetchRadiusKm = radiusKmOverride ?? autoRadiusKm;

  const [trailQuery, setTrailQuery] = useState<{ loading: boolean; error: string | null; items: Trail[] }>({
    loading: true,
    error: null,
    items: []
  });

  useEffect(() => {
    let cancelled = false;
    setTrailQuery((prev) => ({ ...prev, loading: true, error: null }));
    void (async () => {
      try {
        const nearby = await getNearbyTrails(pivotLngLat[1], pivotLngLat[0], trailFetchRadiusKm);
        if (!cancelled) {
          setTrailQuery({ loading: false, error: null, items: nearby });
        }
      } catch (e) {
        if (!cancelled) {
          setTrailQuery({
            loading: false,
            error: e instanceof Error ? e.message : "Failed to load nearby trails.",
            items: []
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pivotLngLat, trailFetchRadiusKm]);

  const handleLocationSelected = useCallback((loc: SelectedLocation) => {
    setSelectedLocation(loc);
  }, []);

  return (
    <div className="space-y-5">
      <SectionCard className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-[0.22em] text-signal">Field Guide</p>
          <h1 className="text-4xl font-extrabold text-appText sm:text-5xl">Explore Trails</h1>
        </div>
        <AppLinkButton
          href="/"
          variant="text"
          className="justify-start px-0 py-0 text-appText hover:text-[#1f3033] sm:min-h-[44px]"
        >
          Back to search
        </AppLinkButton>
      </SectionCard>
      <NearbyTrails
        trails={trailQuery.items}
        trailsLoading={trailQuery.loading}
        trailsLoadError={trailQuery.error}
        onLocationSelected={handleLocationSelected}
        searchRadiusKm={trailFetchRadiusKm}
        autoRadiusKm={autoRadiusKm}
        radiusKmOverride={radiusKmOverride}
        onRadiusKmOverrideChange={setRadiusKmOverride}
        middleSlot={
          <ExploreMap
            embedded
            trails={trailQuery.items}
            trailsLoading={trailQuery.loading}
            trailsError={trailQuery.error}
            pivotLngLat={pivotLngLat}
            selectedLocation={selectedLocation}
            onBrowserPivot={setBrowserPivot}
          />
        }
      />
    </div>
  );
}
