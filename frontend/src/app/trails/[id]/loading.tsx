import { SectionCard } from "@/components/SectionCard";

export default function TrailDetailsLoading() {
  return (
    <div className="space-y-5" aria-busy="true" aria-live="polite">
      <SectionCard className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
          <div className="min-w-0 space-y-3">
            <div className="h-4 w-24 animate-pulse rounded bg-appText/15" aria-hidden />
            <div className="h-10 w-2/3 max-w-md animate-pulse rounded bg-appText/15" aria-hidden />
            <div className="h-5 w-1/2 max-w-sm animate-pulse rounded bg-appText/10" aria-hidden />
          </div>
          <div className="h-5 w-28 shrink-0 animate-pulse rounded bg-appText/15 sm:mt-1" aria-hidden />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="h-20 animate-pulse rounded-lg bg-appText/10" aria-hidden />
          <div className="h-20 animate-pulse rounded-lg bg-appText/10" aria-hidden />
          <div className="h-20 animate-pulse rounded-lg bg-appText/10" aria-hidden />
        </div>
      </SectionCard>
      <SectionCard className="space-y-3">
        <div className="h-8 w-1/2 max-w-xs animate-pulse rounded bg-appText/15" aria-hidden />
        <div className="h-24 animate-pulse rounded-lg bg-appText/10" aria-hidden />
      </SectionCard>
      <SectionCard className="space-y-3">
        <div className="h-8 w-2/5 max-w-xs animate-pulse rounded bg-appText/15" aria-hidden />
        <div className="h-32 animate-pulse rounded-lg bg-appText/10" aria-hidden />
      </SectionCard>
    </div>
  );
}
