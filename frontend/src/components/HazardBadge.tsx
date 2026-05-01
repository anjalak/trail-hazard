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
  snow: "Use traction and start early before slush develops.",
  wildlife: "Keep distance, make noise, and carry bear spray where advised.",
  washout: "Move slowly through unstable sections and use trekking poles.",
  muddy_sections: "Wear waterproof footwear and avoid trail widening."
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
