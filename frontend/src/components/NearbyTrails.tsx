"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useState } from "react";

import { SectionCard } from "@/components/SectionCard";
import { StatusMessage } from "@/components/StatusMessage";
import { EXPLORE_RADIUS_PRESETS, formatExploreRadiusKm } from "@/lib/exploreDefaults";
import { Trail } from "@/types";

type NearbyTrailsProps = {
  trails: Trail[];
  trailsLoading: boolean;
  trailsLoadError: string | null;
  onLocationSelected?: (location: { center: [number, number]; label?: string }) => void;
  /** Rendered after search controls and before the hike list (e.g. the map). */
  middleSlot?: ReactNode;
  searchRadiusKm: number;
  autoRadiusKm: number;
  radiusKmOverride: number | null;
  onRadiusKmOverrideChange: (km: number | null) => void;
};

export function NearbyTrails({
  trails,
  trailsLoading,
  trailsLoadError,
  onLocationSelected,
  middleSlot,
  searchRadiusKm,
  autoRadiusKm,
  radiusKmOverride,
  onRadiusKmOverrideChange
}: NearbyTrailsProps) {
  const token = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN;
  const [status, setStatus] = useState<string>(
    "Map and list stay in sync. Use Find near me or a ZIP/city to narrow hikes."
  );
  const [localBusy, setLocalBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [manualLocationInput, setManualLocationInput] = useState<string>("");

  const controlBusy = localBusy || trailsLoading;
  const controlClassName =
    "min-h-[44px] w-full rounded-md border border-borderSubtle bg-[#f8fbfb] px-3 py-2 text-base text-appText placeholder:text-[#667271] focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 sm:text-sm";

  async function geocodeManualLocation(query: string): Promise<{ center: [number, number]; label: string } | null> {
    if (!token) {
      return null;
    }

    const response = await fetch(
      `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(
        query
      )}.json?access_token=${encodeURIComponent(token)}&autocomplete=true&limit=1&types=postcode,place`
    );
    if (!response.ok) {
      throw new Error("Failed to look up that location. Try another ZIP code or city.");
    }

    const payload = (await response.json()) as {
      features?: Array<{ center?: [number, number]; place_name?: string }>;
    };
    const firstResult = payload.features?.[0];
    const center = firstResult?.center;
    if (!center || center.length !== 2) {
      return null;
    }

    return {
      center: [center[0], center[1]],
      label: firstResult.place_name ?? query
    };
  }

  function findNearby() {
    setLocalError(null);
    setHasSearched(true);
    if (!navigator.geolocation) {
      setLocalError("Geolocation is not supported in this browser.");
      setStatus("Nearby search unavailable.");
      return;
    }

    setStatus("Getting your location...");
    setLocalBusy(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        onLocationSelected?.({ center: [lng, lat], label: "Near your location" });
        setStatus("Searching near your location; list and map will update together.");
        setLocalBusy(false);
      },
      () => {
        setLocalError("Location permission denied. Enable location and try again.");
        setStatus("Nearby search unavailable.");
        setLocalBusy(false);
      }
    );
  }

  async function findNearbyByManualLocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    setHasSearched(true);
    const query = manualLocationInput.trim();
    if (!query) {
      setLocalError("Enter a ZIP code or city.");
      return;
    }
    if (!token) {
      setLocalError("Manual location search requires a map token. Add NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN.");
      return;
    }

    setLocalBusy(true);
    setStatus("Finding that location...");

    try {
      const result = await geocodeManualLocation(query);
      if (!result) {
        setLocalError("No matching location found. Try a different ZIP code or city.");
        setStatus("Manual location search unavailable.");
        return;
      }

      setStatus(`Loading hikes for ${result.label}…`);
      onLocationSelected?.({ center: result.center, label: result.label });
    } catch (lookupError) {
      setLocalError(lookupError instanceof Error ? lookupError.message : "Failed to look up that location.");
      setStatus("Manual location search failed.");
    } finally {
      setLocalBusy(false);
    }
  }

  return (
    <SectionCard className="space-y-4" labelledBy="nearby-hikes-heading">
      <div className="flex flex-col gap-3">
        <h2 id="nearby-hikes-heading" className="text-2xl text-appText">
          Nearby hikes
        </h2>
        <StatusMessage message={status} role="status" ariaLive="polite" className="text-sm text-slate-600" />
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => findNearby()}
            disabled={controlBusy}
            aria-busy={controlBusy}
            className="min-h-[44px] w-full shrink-0 rounded-md border border-accent bg-[#1f3033] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:border-accentSoft hover:bg-[#17282a] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 disabled:opacity-60 sm:w-auto sm:py-2"
          >
            {controlBusy ? "Finding..." : "Find near me"}
          </button>
          <form className="flex flex-col gap-2 sm:flex-row sm:items-end" onSubmit={findNearbyByManualLocation}>
            <div className="min-w-0 flex-1">
              <label htmlFor="nearby-manual-location" className="mb-1 block text-sm font-medium text-[#26373a]">
                ZIP code or city
              </label>
              <input
                id="nearby-manual-location"
                type="text"
                value={manualLocationInput}
                onChange={(event) => setManualLocationInput(event.target.value)}
                placeholder="e.g. 98104 or Seattle"
                className={controlClassName}
              />
            </div>
            <button
              type="submit"
              disabled={controlBusy}
              className="min-h-[44px] rounded-md border border-accent bg-[#1f3033] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:border-accentSoft hover:bg-[#17282a] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {controlBusy ? "Searching..." : "Use entered location"}
            </button>
          </form>
          <div className="space-y-1.5">
            <label htmlFor="explore-search-radius" className="block text-sm font-medium text-[#26373a]">
              Search radius
            </label>
            <p className="text-sm text-[#364547]" id="explore-search-radius-desc">
              Showing trails within{" "}
              <strong className="font-semibold text-appText">{formatExploreRadiusKm(searchRadiusKm)}</strong>
              {radiusKmOverride === null ? (
                <span className="text-[#5c6766]"> (automatic for your current map center)</span>
              ) : (
                <span className="text-[#5c6766]"> (custom)</span>
              )}
            </p>
            <select
              id="explore-search-radius"
              aria-describedby="explore-search-radius-desc"
              className={controlClassName}
              value={
                radiusKmOverride === null
                  ? "auto"
                  : (() => {
                      const hit = EXPLORE_RADIUS_PRESETS.find(
                        (p) => Math.abs(p.km - radiusKmOverride) < 0.05
                      );
                      return hit ? String(hit.km) : String(radiusKmOverride);
                    })()
              }
              onChange={(event) => {
                const v = event.target.value;
                if (v === "auto") {
                  onRadiusKmOverrideChange(null);
                  return;
                }
                onRadiusKmOverrideChange(Number(v));
              }}
            >
              <option value="auto">
                Automatic — {formatExploreRadiusKm(autoRadiusKm)}
              </option>
              {EXPLORE_RADIUS_PRESETS.map((p) => (
                <option key={`${p.km}-${p.label}`} value={String(p.km)}>
                  {p.label} ({formatExploreRadiusKm(p.km)})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
      {(localError ?? trailsLoadError) ? (
        <StatusMessage
          className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700"
          message={localError ?? trailsLoadError ?? ""}
          role="alert"
        />
      ) : null}
      {middleSlot ? <div className="space-y-3">{middleSlot}</div> : null}
      {hasSearched && !trailsLoading && !localError && !trailsLoadError && trails.length === 0 ? (
        <StatusMessage
          message='No hikes in results. Tap "Find near me" or try another ZIP/city.'
          tone="muted"
        />
      ) : null}
      {trails.length ? (
        <ul className="space-y-2">
          {trails.map((trail) => (
            <li key={trail.id} className="rounded-md border border-borderSubtle bg-[#f2f6f5]">
              <Link
                href={`/trails/${trail.id}`}
                className="flex min-h-[44px] w-full flex-col justify-center gap-0.5 px-3 py-2 font-medium text-appText underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 sm:min-h-0 sm:py-3"
              >
                <span>{trail.name}</span>
                <span className="text-sm font-normal text-[#364547]">
                  {trail.region} - {trail.difficulty} - {trail.length_km} km
                </span>
                {trail.location ? (
                  <span className="text-sm font-normal text-[#5c6766]">
                    {trail.location.city ?? "Unknown city"}, {trail.location.state_code}
                    {trail.location.park_name ? ` - ${trail.location.park_name}` : ""}
                  </span>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </SectionCard>
  );
}
