import type { Metadata } from "next";
import Link from "next/link";

import { AppLinkButton } from "@/components/AppLinkButton";
import { SectionCard } from "@/components/SectionCard";

export const metadata: Metadata = {
  title: "About — TrailIntel",
  description: "Why TrailIntel exists: clearer trail search and honest risk context for hikers."
};

export default function AboutPage() {
  return (
    <div className="space-y-5">
      <SectionCard className="space-y-4">
        <header className="space-y-3">
          <p className="text-xs uppercase tracking-[0.22em] text-signal">About</p>
          <h1 className="max-w-3xl text-4xl font-extrabold text-appText sm:text-5xl">Why this site exists</h1>
          <p className="max-w-3xl text-sm text-[#3c4a4b] sm:text-base">
            I built TrailIntel because finding a hike and getting a guage of potential hazards usually means jumping between park
            pages, forums, and maps that are often outdated and filled with old reviews and information. I wanted a unified place to quickly get an idea
            of trail conditions as I'm planning my next hike. Trail Intel allows for trail search, scanning nearby options,
            and seeing an at a glance view of the current danger levels alongside practical guidance. This is not a replacement for
            official land-manager communications or real-time conditions on the ground, but is one step in the planning process for 
            trail traversals and helping to give people the resources they need to make informed decisions and have safe outdoor adventures!
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
      </SectionCard>

      <SectionCard as="article" className="space-y-3">
        <h2 className="text-2xl text-appText">What you should expect</h2>
        <p className="text-sm leading-relaxed text-[#263638]">
          The goal is faster orientation and clearer risk framing for everyday trip planning — especially where coverage
          is growing from a Washington-heavy MVP toward broader trails. If something here conflicts with a closure,
          bulletin, or ranger guidance, trust the authoritative source.
        </p>
        <p className="text-sm leading-relaxed text-[#263638]">
          For how trail listings and hazard signals are assembled (and what timestamps mean), see{" "}
          <Link
            className="font-medium text-accent underline decoration-accent/50 underline-offset-2 hover:decoration-accent"
            href="/sources"
          >
            Data sources
          </Link>
          .
        </p>
      </SectionCard>
    </div>
  );
}
