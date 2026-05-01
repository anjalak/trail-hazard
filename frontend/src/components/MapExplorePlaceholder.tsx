type Props = {
  note?: string;
};

export function MapExplorePlaceholder({ note }: Props) {
  return (
    <section className="space-y-3 rounded-xl bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold">Map explore</h2>
      <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50">
        <p className="text-sm text-slate-600">
          Mapbox integration placeholder: trail markers, hazard overlays, and cluster styling.
        </p>
      </div>
      <p className="text-sm text-slate-500">
        {note ?? "Next step: add Mapbox GL JS layer for hazards and click-through to trail detail."}
      </p>
    </section>
  );
}
