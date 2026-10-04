import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const styles: Record<Variant, string> = {
  primary:
    "bg-ember text-bg-0 hover:bg-ember-hi disabled:bg-bg-3 disabled:text-fg-3 font-medium",
  secondary:
    "bg-bg-2 text-fg-0 border border-line-strong hover:border-fg-3 disabled:text-fg-3",
  ghost: "text-fg-1 hover:text-fg-0 hover:bg-bg-2",
};

export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`inline-flex h-8 items-center justify-center gap-2 rounded-ctl px-3 text-[13px] transition-colors duration-150 ease-out disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...props}
    />
  );
}
