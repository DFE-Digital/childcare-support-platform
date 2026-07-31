import type { ReactNode } from "react";

interface ExternalLinkProps {
  href: string;
  showIcon?: boolean;
  className?: string;
  children: ReactNode;
  tabIndex?: number;
}

export function ExternalLink({
  href,
  showIcon = true,
  className = "",
  children,
  tabIndex,
}: ExternalLinkProps) {
  const hasUnderline = className.includes("underline");
  const linkClass = hasUnderline
    ? className.replace(/\bunderline\b/, "").trim()
    : className;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={linkClass}
      tabIndex={tabIndex}
    >
      <span className={hasUnderline ? "underline" : undefined}>{children}</span>
      {showIcon && (
        <>
          {" "}
          <i className="bi bi-box-arrow-up-right" aria-hidden="true" />
        </>
      )}
      <span className="sr-only">(opens in new tab)</span>
    </a>
  );
}
