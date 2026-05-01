type StatusMessageProps = {
  message: string;
  tone?: "default" | "error" | "muted";
  role?: "status" | "alert";
  id?: string;
  ariaLive?: "off" | "polite" | "assertive";
  className?: string;
};

const toneStyles: Record<NonNullable<StatusMessageProps["tone"]>, string> = {
  default: "text-sm text-[#4a5758]",
  error: "text-sm text-red-600",
  muted: "rounded-md border border-borderSubtle bg-surfaceMuted p-3 text-sm text-[#586465]"
};

export function StatusMessage({
  message,
  tone = "default",
  role = "status",
  id,
  ariaLive,
  className
}: StatusMessageProps) {
  return (
    <p id={id} role={role} aria-live={ariaLive} className={[toneStyles[tone], className].filter(Boolean).join(" ")}>
      {message}
    </p>
  );
}
