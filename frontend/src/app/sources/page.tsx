import type { Metadata } from "next";

import { AppLinkButton } from "@/components/AppLinkButton";
import { SectionCard } from "@/components/SectionCard";

export const metadata: Metadata = {
  title: "Data sources — TrailIntel",
  description:
    "Where TrailIntel trail and hazard data comes from, how to read timestamps, and limitations for trip planning."
};

export default function SourcesPage() {
  return (
    <div className="space-y-5">
      <SectionCard className="space-y-4">
        <header className="space-y-3">
          <p className="text-xs uppercase tracking-[0.22em] text-signal">Transparency</p>
          <h1 className="max-w-3xl text-4xl font-extrabold text-appText sm:text-5xl">Data sources</h1>
          <p className="max-w-3xl text-sm text-[#3c4a4b] sm:text-base">
            TrailIntel combines public trail and park information, for example National Park Service developer APIs and
            published park alerts, with an internal pipeline that normalizes text, tags hazard types, and scores recency
            so the site can surface consistent badges and copy. It does not claim completeness or real-time coverage
            across every trail network.
          </p>
        </header>
        <div className="flex flex-col gap-2 sm:flex-row">
          <AppLinkButton href="/" variant="outline" className="w-full sm:w-auto">
            Back to search
          </AppLinkButton>
          <AppLinkButton href="/about" variant="outline" className="w-full sm:w-auto">
            About
          </AppLinkButton>
        </div>
      </SectionCard>

      <SectionCard as="article" className="space-y-3">
        <h2 className="text-2xl text-appText">Informational, not safety-critical</h2>
        <p className="text-sm leading-relaxed text-[#263638]">
          Everything here is an aid for planning and orientation. Conditions change with weather, maintenance, wildlife,
          and human factors this site cannot observe. Nothing on TrailIntel is a substitute for official closures,
          permits, route briefings, or your own judgment in the field. When in doubt, follow posted signage and
          guidance from land managers and emergency services.
        </p>
      </SectionCard>

      <SectionCard as="article" className="space-y-3">
        <h2 className="text-2xl text-appText">What “last refreshed” means on trail pages</h2>
        <p className="text-sm leading-relaxed text-[#263638]">
          Trail detail views show timestamps tied to specific signals — for example when a hazard observation was
          recorded or when a weather snapshot was fetched. Those labels describe the last time we ingested or retrieved
          that piece of data, not a live guarantee of conditions at this moment and not a monitoring cadence for every
          trail system.
        </p>
        <p className="text-sm leading-relaxed text-[#263638]">
          If a section notes that recent hazard information is missing, treat that as a gap in our dataset for that hike,
          not proof that the trail is hazard-free.
        </p>
      </SectionCard>

      <SectionCard as="article" className="space-y-3">
        <h2 className="text-2xl text-appText">Authoritative sources</h2>
        <p className="text-sm leading-relaxed text-[#263638]">
          For closures, regulations, and safety-critical updates, rely on the managing agency (for example NPS, USFS,
          state parks, or local land trusts) and their official channels. TrailIntel is meant to complement that
          workflow, not replace it.
        </p>
      </SectionCard>
    </div>
  );
}
