export default function TrailDetailsLoading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-live="polite">
      <div className="h-5 w-28 animate-pulse rounded bg-slate-200" aria-hidden="true" />
      <section className="space-y-3 rounded-xl bg-white p-4 shadow-sm sm:p-6">
        <div className="h-7 w-2/3 animate-pulse rounded bg-slate-200" aria-hidden="true" />
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="h-20 animate-pulse rounded-lg bg-slate-100" aria-hidden="true" />
          <div className="h-20 animate-pulse rounded-lg bg-slate-100" aria-hidden="true" />
          <div className="h-20 animate-pulse rounded-lg bg-slate-100" aria-hidden="true" />
        </div>
      </section>
      <section className="h-56 animate-pulse rounded-xl bg-slate-100" aria-hidden="true" />
      <section className="h-56 animate-pulse rounded-xl bg-slate-100" aria-hidden="true" />
    </div>
  );
}
