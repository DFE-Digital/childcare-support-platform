import { useState, useEffect, useRef } from "react";
import { Container } from "./Container";
import logoLight from "@/assets/logo-light.webp";
import ukGov from "@/assets/uk-gov.png";

const navLinks = [
  { label: "PREGNANCY", href: "https://beststartinlife.gov.uk/pregnancy/" },
  { label: "BABY", href: "https://beststartinlife.gov.uk/baby/" },
  { label: "TODDLER", href: "https://beststartinlife.gov.uk/toddler/" },
  {
    label: "CHILDCARE & EARLY YEARS EDUCATION",
    href: "https://beststartinlife.gov.uk/childcare-early-years-education/",
  },
  {
    label: "SCHOOL READINESS",
    href: "https://beststartinlife.gov.uk/childcare-early-years-education/",
  },
];

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!mobileOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMobileOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [mobileOpen]);

  return (
    <header className="bg-white shadow-sm relative z-50">
      <Container>
        <div className="flex items-center justify-between py-4 gap-4">
          {/* Logos */}
          <a
            href="https://beststartinlife.gov.uk/"
            className="flex items-center gap-4 shrink-0"
          >
            <img
              src={logoLight}
              alt="Best Start In Life"
              className="h-[54px] w-auto"
            />
            <img
              src={ukGov}
              alt=""
              className="hidden sm:block h-[54px] w-auto"
            />
          </a>

          {/* Desktop nav */}
          <nav
            className="hidden xl:flex items-center gap-6"
            aria-label="Main navigation"
          >
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-base font-bold text-neutral-700 tracking-wide hover:text-purple-800 transition-colors whitespace-nowrap"
              >
                {link.label}
              </a>
            ))}
          </nav>

          {/* Mobile menu toggle */}
          <button
            ref={toggleRef}
            className="xl:hidden flex items-center justify-center gap-x-3 border-2 border-neutral-700 rounded-full px-4 py-2"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle navigation menu"
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav"
          >
            {mobileOpen ? (
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
              >
                <path
                  d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z"
                  fill="currentColor"
                />
              </svg>
            ) : (
              <svg
                width="12"
                height="12"
                viewBox="0 0 12 12"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
              >
                <path
                  d="M0 1H12M12 11H0M12 6H6H0"
                  stroke="currentColor"
                  strokeWidth="2"
                />
              </svg>
            )}
            <span className="text-base font-bold uppercase">
              {mobileOpen ? "Close" : "Menu"}
            </span>
          </button>
        </div>

        {/* Mobile nav */}
        {mobileOpen && (
          <nav
            id="mobile-nav"
            aria-label="Main navigation"
            className="xl:hidden border-t border-zinc-200 py-4 space-y-3"
          >
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="block text-right text-base font-bold text-neutral-700 py-1"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </a>
            ))}
          </nav>
        )}
      </Container>
    </header>
  );
}
