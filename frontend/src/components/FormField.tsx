import { ReactNode } from "react";

type FormFieldProps = {
  id: string;
  label: string;
  children: ReactNode;
  className?: string;
};

export function FormField({ id, label, children, className }: FormFieldProps) {
  return (
    <label htmlFor={id} className={["space-y-1 text-sm text-[#364547]", className].filter(Boolean).join(" ")}>
      <span className="font-medium">{label}</span>
      {children}
    </label>
  );
}
