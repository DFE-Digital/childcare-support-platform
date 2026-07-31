import type { ReactNode } from "react";

export function Container({
  children,
  className = "",
  maxWidth = 1440,
}: {
  children: ReactNode;
  className?: string;
  maxWidth?: number;
}) {
  return (
    <div className={`mx-auto px-5 md:px-7 ${className}`} style={{ maxWidth }}>
      {children}
    </div>
  );
}
