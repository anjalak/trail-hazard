import Link from "next/link";
import { ReactNode } from "react";

type AppLinkButtonProps = {
  href: string;
  children: ReactNode;
  className?: string;
  variant?: "primary" | "outline" | "text";
};

const variantStyles: Record<NonNullable<AppLinkButtonProps["variant"]>, string> = {
  primary:
    "border border-accent bg-brand font-semibold text-white shadow-sm hover:border-accentSoft hover:bg-[#243538] focus-visible:ring-focusRing focus-visible:ring-offset-appBg",
  outline:
    "border border-borderSubtle bg-surface text-appText hover:border-accent hover:bg-surfaceMuted focus-visible:ring-focusRing focus-visible:ring-offset-appBg",
  text: "text-[#f4ede3] underline decoration-accent/60 underline-offset-4 hover:text-accent hover:decoration-accent focus-visible:ring-focusRing focus-visible:ring-offset-appBg"
};

export function AppLinkButton({ href, children, className, variant = "outline" }: AppLinkButtonProps) {
  const baseClassName =
    "inline-flex min-h-[44px] items-center justify-center rounded-md px-4 py-2.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2";
  const linkClassName = [baseClassName, variantStyles[variant], className].filter(Boolean).join(" ");

  return (
    <Link href={href} className={linkClassName}>
      {children}
    </Link>
  );
}
