import Link from "next/link";

import { AppLinkButton } from "@/components/AppLinkButton";
import { SearchBar } from "@/components/SearchBar";
import { SectionCard } from "@/components/SectionCard";

export default function HomePage() {
  return (
    <div className="space-y-5 sm:space-y-6">
      <SectionCard className="space-y-4 overflow-hidden">
        <header className="space-y-3">
          <p className="text-xs uppercase tracking-[0.22em] text-[#54605f]">Curated Trail Intelligence</p>
          <h1 className="max-w-3xl text-4xl font-extrabold text-appText sm:text-5xl">
            Discover quieter paths with clearer risk context.
          </h1>
          <p className="max-w-2xl text-sm text-[#3c4a4b] sm:text-base">
            Find hikes quickly and understand trail risks with recent condition reports, hazard badges, and practical
            guidance. MVP content is densest around Washington as we grow nationwide coverage.
          </p>
        </header>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs uppercase tracking-[0.16em] text-signal">Search first, then explore nearby routes</p>
          <AppLinkButton
            href="/explore"
            variant="primary"
            className="w-full sm:w-auto sm:justify-start"
          >
            Explore map + nearby hikes
          </AppLinkButton>
        </div>
        <p className="text-xs text-[#3c4a4b]">
          Building with trail data?{" "}
          <Link className="underline decoration-accent/70 underline-offset-4 hover:text-accent" href="/api">
            View the GraphQL and robotics API guide
          </Link>
          .
        </p>
      </SectionCard>

      <SectionCard className="space-y-3">
        <h2 className="text-2xl text-appText">Trail Search</h2>
        <SearchBar />
      </SectionCard>
    </div>
  );
}
