import { Link } from "react-router-dom";
import type { ReactNode, ButtonHTMLAttributes } from "react";

type Variant = "default" | "dark" | "purple" | "tertiary" | "white" | "outline";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  to?: string;
  href?: string;
  children: ReactNode;
  arrow?: boolean;
  className?: string;
}

const variantClass: Record<Variant, string> = {
  default: "btn",
  dark: "btn-dark",
  purple: "btn-purple",
  tertiary: "btn-tertiary",
  white: "btn-white",
  outline: "btn-outline",
};

export function Button({
  variant = "default",
  to,
  href,
  children,
  arrow,
  className = "",
  ...rest
}: ButtonProps) {
  const cls = `${variantClass[variant]} ${className}`;
  const internalContent = (
    <>
      {children}
      {arrow && <span aria-hidden="true">&rarr;</span>}
    </>
  );
  const externalContent = (
    <>
      {children}
      {arrow && <i className="bi bi-box-arrow-up-right" aria-hidden="true" />}
    </>
  );

  if (to)
    return (
      <Link to={to} className={cls}>
        {internalContent}
      </Link>
    );
  if (href)
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>
        {externalContent}
        <span className="sr-only">(opens in new tab)</span>
      </a>
    );
  return (
    <button className={cls} {...rest}>
      {internalContent}
    </button>
  );
}
