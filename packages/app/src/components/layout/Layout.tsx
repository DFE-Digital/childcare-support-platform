import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { usePostHog } from "posthog-js/react";
import { FamilyProvider } from "@/context/FamilyContext";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useDeployFreshness } from "@/hooks/useDeployFreshness";
import { Header } from "./Header";
import { Footer } from "./Footer";
import { Container } from "./Container";

const navLinks = [
  { label: "Home", shortLabel: "Home", to: "/" },
  { label: "Get Support", shortLabel: "Support", to: "/support" },
  { label: "Estimate Costs", shortLabel: "Costs", to: "/costs" },
  { label: "Find a Provider", shortLabel: "Providers", to: "/providers" },
];

function isActive(linkTo: string, pathname: string): boolean {
  if (linkTo === "/") return pathname === "/";
  return pathname === linkTo || pathname.startsWith(linkTo + "/");
}

function StickyNav() {
  const { pathname } = useLocation();
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    const goOffline = () => setIsOffline(true);
    const goOnline = () => setIsOffline(false);
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, []);

  return (
    <div id="sticky-header" className="bg-purple-50 sticky top-0 z-40">
      <Container>
        <div className="flex items-center justify-center gap-1 py-2">
          <nav
            className="flex items-center gap-1"
            aria-label="Checker navigation"
          >
            {navLinks.map((link) => {
              const active = isActive(link.to, pathname);
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`text-xs min-[560px]:text-base font-bold transition-colors px-2 min-[500px]:px-3 py-1 rounded-full ${
                    active
                      ? "bg-purple-800 text-white"
                      : "text-purple-800 hover:text-purple-600 hover:bg-purple-100"
                  }`}
                  aria-current={active ? "page" : undefined}
                >
                  <span className="hidden sm:inline">{link.label}</span>
                  <span className="sm:hidden">{link.shortLabel}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </Container>
      {isOffline && (
        <div
          role="alert"
          className="bg-purple-800 text-white text-center text-sm py-1.5"
        >
          <i className="bi bi-exclamation-triangle-fill" aria-hidden="true" />{" "}
          Network unavailable — will retry when connection restores
        </div>
      )}
    </div>
  );
}

function PostHogPageview() {
  const { pathname, search } = useLocation();
  const posthog = usePostHog();

  useEffect(() => {
    if (posthog) {
      posthog.capture("$pageview", { $current_url: pathname + search });
    }
  }, [pathname, search, posthog]);

  return null;
}

function ScrollToTop() {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if ("scrollRestoration" in window.history) {
      window.history.scrollRestoration = "manual";
    }
  }, []);

  useEffect(() => {
    if (hash === "#main-content") {
      document.getElementById("page-hero")?.scrollIntoView({ block: "start" });
      document.getElementById("main-content")?.focus();
    } else {
      window.scrollTo(0, 0);
    }
  }, [pathname, hash]);
  return null;
}

export function Layout() {
  useDeployFreshness();

  return (
    <FamilyProvider>
      <PostHogPageview />
      <ScrollToTop />
      <div className="min-h-screen flex flex-col">
        <a
          href="#main-content"
          onClick={(e) => {
            e.preventDefault();
            const hero = document.getElementById("page-hero");
            const heading = document.getElementById("main-content");
            hero?.scrollIntoView({ block: "start" });
            heading?.focus();
          }}
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[9999] focus:bg-purple-800 focus:text-white focus:px-4 focus:py-2 focus:rounded-full focus:outline-none focus:shadow-[0_0_0_3px_white,0_0_0_6px_#3b82f6]"
        >
          Skip to main content
        </a>
        <Header />
        <StickyNav />
        <main className="flex-1">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
        <Footer />
      </div>
    </FamilyProvider>
  );
}
