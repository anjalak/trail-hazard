/** Statute miles to kilometres (same factor as elsewhere in this module). */
export const KM_PER_STATUTE_MI = 1.609344;

/** Mapbox ordering: [longitude, latitude] — central Cascades foothills until the user chooses a location. */
export const DEFAULT_EXPLORE_CENTER: [number, number] = [-121.661, 47.466];

/** ~25 statute miles — list + map use this radius after ZIP/city, or “Find near me”. */
export const USER_NEARBY_RADIUS_KM = 25 * KM_PER_STATUTE_MI;

/**
 * Wide enough to include seeded demo trails from around the default WA center before the visitor narrows location.
 */
export const DEFAULT_EXPLORE_RADIUS_KM = 200;

/** Rounded label for UI (kilometres primary, miles in parentheses). */
export function formatExploreRadiusKm(km: number): string {
  const mi = km / KM_PER_STATUTE_MI;
  const kmRounded = km >= 100 ? Math.round(km) : Math.round(km * 10) / 10;
  const miRounded = mi >= 100 ? Math.round(mi) : Math.round(mi * 10) / 10;
  return `${kmRounded} km (${miRounded} mi)`;
}

/**
 * Preset radii for the explore search control (values in km).
 * Includes the two automatic defaults via explicit entries.
 */
export const EXPLORE_RADIUS_PRESETS: { km: number; label: string }[] = [
  { km: 10 * KM_PER_STATUTE_MI, label: "10 mi" },
  { km: 25 * KM_PER_STATUTE_MI, label: "25 mi" },
  { km: 50 * KM_PER_STATUTE_MI, label: "50 mi" },
  { km: 75 * KM_PER_STATUTE_MI, label: "75 mi" },
  { km: 100 * KM_PER_STATUTE_MI, label: "100 mi" },
  { km: 150 * KM_PER_STATUTE_MI, label: "150 mi" },
  { km: 200 * KM_PER_STATUTE_MI, label: "200 mi" },
  { km: DEFAULT_EXPLORE_RADIUS_KM, label: "200 km (wide)" }
];
