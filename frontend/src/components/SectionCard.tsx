import { ReactNode } from "react";

type SectionCardProps = {
  children: ReactNode;
  className?: string;
  as?: "section" | "article" | "div";
  labelledBy?: string;
  id?: string;
};

export function SectionCard({ children, className, as = "section", labelledBy, id }: SectionCardProps) {
  const Component = as;
  const cardClassName = [
    "rounded-panel border border-borderSubtle bg-surface p-4 shadow-card sm:p-5",
    className
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Component id={id} aria-labelledby={labelledBy} className={cardClassName}>
      {children}
    </Component>
  );
}
