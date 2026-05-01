import { AppLinkButton } from "@/components/AppLinkButton";
import { HazardBadge } from "@/components/HazardBadge";
import { SectionCard } from "@/components/SectionCard";
import { StatusMessage } from "@/components/StatusMessage";
import { getNearbyTrails, getTrailConditions } from "@/lib/graphql";

type TrailPageProps = {
  params: { id: string };
};

function formatSeenDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown date";
  }
  return parsed.toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

export default async function TrailPage({ params }: TrailPageProps) {
  const trailId = Number(params.id);
  const conditions = await getTrailConditions(trailId);

  if (!conditions) {
    return (
      <div className="space-y-4">
        <p className="text-lg font-semibold text-appText">Trail not found.</p>
        <AppLinkButton href="/" variant="text" className="justify-start px-0 py-0">
          Back to search
        </AppLinkButton>
      </div>
    );
  }

  const shouldLoadNearby = !conditions.has_recent_info && conditions.lat != null && conditions.lng != null;
  const nearbyFallback = shouldLoadNearby ? await getNearbyTrails(conditions.lat!, conditions.lng!, 25) : [];
  const nearbyHikes = nearbyFallback.filter((trail) => trail.id !== trailId).slice(0, 5);
  const locationParts = [
    conditions.location?.park_name,
    conditions.location?.city,
    conditions.location?.state_code
  ].filter(Boolean);

  return (
    <div className="space-y-5">
      <AppLinkButton href="/" variant="text" className="justify-start px-0 py-0">
        Back to search
      </AppLinkButton>

      <SectionCard labelledBy="trail-summary-heading" className="space-y-3">
        <p className="text-xs uppercase tracking-[0.22em] text-signal">Trail Brief</p>
        <h1 id="trail-summary-heading" className="text-4xl font-extrabold text-appText sm:text-5xl">
          {conditions.name}
        </h1>
        <p className="text-sm font-medium text-[#3c4a4b]">
          {locationParts.length ? locationParts.join(" - ") : `${conditions.region} region`}
        </p>
        <dl className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-borderSubtle bg-surfaceMuted p-3">
            <dt className="text-xs uppercase tracking-[0.14em] text-[#5c6766]">Overall risk score</dt>
            <dd className="mt-1 text-xl font-semibold text-appText">{conditions.overall_score}/100</dd>
          </div>
          <div className="rounded-lg border border-borderSubtle bg-surfaceMuted p-3">
            <dt className="text-xs uppercase tracking-[0.14em] text-[#5c6766]">Active hazards</dt>
            <dd className="mt-1 text-xl font-semibold text-appText">{conditions.hazard_summary.active_count}</dd>
          </div>
          <div className="rounded-lg border border-borderSubtle bg-surfaceMuted p-3">
            <dt className="text-xs uppercase tracking-[0.14em] text-[#5c6766]">Highest severity</dt>
            <dd className="mt-1 text-xl font-semibold capitalize text-appText">
              {conditions.hazard_summary.highest_severity}
            </dd>
          </div>
        </dl>
      </SectionCard>

      <SectionCard as="article" labelledBy="trail-hazards-heading" className="space-y-4">
        <header>
          <h2 id="trail-hazards-heading" className="text-2xl text-appText">
            Hazards and guidance
          </h2>
          <p className="text-sm text-[#3c4a4b]">Current danger badges and how to prepare before you head out.</p>
        </header>
        {conditions.hazard_summary.types.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {conditions.hazard_summary.types.map((type) => (
              <HazardBadge key={type} type={type} severity={conditions.hazard_summary.highest_severity} />
            ))}
          </div>
        ) : (
          <StatusMessage message="No active hazards currently reported." tone="muted" />
        )}
      </SectionCard>

      <SectionCard labelledBy="trail-weather-heading" className="space-y-3">
        <h2 id="trail-weather-heading" className="text-2xl text-appText">
          Current weather snapshot
        </h2>
        {conditions.weather_snapshot ? (
          <div className="rounded-lg border border-borderSubtle bg-[#f2f6f5] p-3 text-sm text-[#2f3d3f]">
            <p className="font-medium">{conditions.weather_snapshot.summary}</p>
            <p className="mt-1">
              Temp: {conditions.weather_snapshot.temperature_c ?? "n/a"} C | Wind:{" "}
              {conditions.weather_snapshot.wind_kph ?? "n/a"} kph
            </p>
            <p className="mt-1 text-xs text-[#5c6766]">Updated {formatSeenDate(conditions.weather_snapshot.fetched_at)}</p>
            <p className="text-xs text-[#5c6766]">
              Refreshes after {formatSeenDate(conditions.weather_snapshot.expires_at)}
            </p>
          </div>
        ) : (
          <StatusMessage message="Weather provider data is temporarily unavailable." tone="muted" />
        )}
      </SectionCard>

      {conditions.has_recent_info ? (
        <SectionCard labelledBy="trail-observations-heading" className="space-y-3">
          <h2 id="trail-observations-heading" className="text-2xl text-appText">
            Recent hazard observations
          </h2>
          {conditions.active_hazards.length ? (
            <ul className="space-y-2">
              {conditions.active_hazards.map((hazard) => {
                return (
                  <li key={hazard.id} className="rounded-md border border-borderSubtle bg-[#f2f6f5] p-3 text-sm">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                    <p className="font-medium capitalize">{hazard.type.replace(/_/g, " ")}</p>
                    <p className="shrink-0 text-xs text-signal">Seen {formatSeenDate(hazard.reported_at)}</p>
                  </div>
                  <p className="mt-1 text-[#2f3d3f]">{hazard.raw_text ?? "No details provided."}</p>
                  <p className="mt-1 text-[#5c6766]">Signal source: {hazard.source}</p>
                  </li>
                );
              })}
            </ul>
          ) : (
            <StatusMessage message="No hazard observations available for this hike right now." tone="muted" />
          )}
        </SectionCard>
      ) : null}

      {!conditions.has_recent_info ? (
        <SectionCard labelledBy="trail-no-recent-info-heading" className="space-y-3">
          <h2 id="trail-no-recent-info-heading" className="text-2xl text-appText">
            No recent info for this hike
          </h2>
          <StatusMessage
            message="We do not have fresh hazard signals for this trail yet. Check nearby hikes for relative conditions."
            tone="muted"
          />
          {nearbyHikes.length ? (
            <ul className="space-y-2">
              {nearbyHikes.map((trail) => (
                <li key={trail.id} className="rounded-md border border-borderSubtle bg-[#f2f6f5] p-3 text-sm">
                  <a href={`/trails/${trail.id}`} className="font-medium text-appText underline">
                    {trail.name}
                  </a>
                  <p className="mt-1 text-[#5c6766]">
                    {trail.location?.city ?? "Unknown city"}, {trail.location?.state_code ?? "Unknown state"}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <StatusMessage message="No nearby hikes available from this location yet." tone="muted" />
          )}
          <AppLinkButton href="/explore" variant="primary">
            See nearby hikes on map
          </AppLinkButton>
        </SectionCard>
      ) : null}

      <SectionCard labelledBy="trail-reports-status-heading" className="space-y-2">
        <h2 id="trail-reports-status-heading" className="text-lg text-appText">
          Reports status
        </h2>
        <StatusMessage
          message="Account-based reviews and report submissions are deferred until user accounts and moderation controls are enabled."
          tone="default"
          className="text-xs text-[#5c6766]"
        />
      </SectionCard>
    </div>
  );
}
