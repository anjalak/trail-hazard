type Props = {
  type: string;
  severity: "low" | "medium" | "high";
};

const severityStyles = {
  low: "bg-[#d6ece7] text-[#24554f]",
  medium: "bg-[#e9f3b8] text-[#4b5f19]",
  high: "bg-[#edd2c7] text-[#7f3b2f]"
};

const guidanceByType: Record<string, string> = {
  avalanche: "Avoid avalanche terrain; check forecasts and carry proper gear.",
  severe_weather: "Seek shelter from lightning; avoid exposed ridges and lone trees.",
  mass_movement: "Avoid slopes with debris flows or fresh slide tracks; turn back if unstable.",
  bridge: "Verify crossing safety; scout for detours if the structure is damaged or gone.",
  closure: "Do not enter closed areas; use official notices for reopening.",
  snow: "Use traction and start early before slush develops.",
  wet: "Expect reduced grip; consider poles and tread with deeper lugs.",
  muddy_sections: "Wear waterproof footwear and avoid trail widening.",
  washout: "Move slowly through unstable sections and use trekking poles.",
  flooding: "Avoid crossing moving water; turn back if the route is submerged.",
  rockfall: "Move quickly through exposure zones and watch for debris from above.",
  wildlife: "Keep distance, make noise, and carry bear spray where advised.",
  downed_tree: "Plan extra time to bypass or step over; watch for sharp branches.",
  ice: "Use traction devices and avoid steep ice without protection."
};

export function HazardBadge({ type, severity }: Props) {
  const guidance = guidanceByType[type] ?? "Proceed carefully and review the latest trail reports.";

  return (
    <div className="rounded-lg border border-borderSubtle bg-[#f2f6f5] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-medium capitalize text-appText">{type.replaceAll("_", " ")}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${severityStyles[severity]}`}>{severity}</span>
      </div>
      <p className="text-sm text-[#364547]">{guidance}</p>
    </div>
  );
}
