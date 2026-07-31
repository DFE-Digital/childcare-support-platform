/**
 * Deploy-freshness auto-reload hook.
 *
 * PRODUCTION ONLY — this hook is inert during development (Vite HMR handles
 * code updates). In production it detects when a new deploy has landed and
 * automatically reloads the page, clearing all in-memory caches at once.
 *
 * ## Why this exists
 *
 * Code and data are always deployed together (via `prod/deploy-bsil`). The app
 * holds provider data, SIS responses, postcode lookups, and schema objects in
 * module-level variables, useRef Maps, and useState — none of which expire.
 * If a user leaves a browser tab open across a deploy, they run stale code
 * against potentially new data. The worst case is an SIS schema mismatch where
 * old parsing code reads a new binary column layout.
 *
 * A page reload destroys the entire JS context, so every cache is cleared in
 * one shot — no need to add TTLs or invalidation to each cache individually.
 *
 * ## How it works
 *
 * On mount, the hook fetches `index.html` and stores its ETag (or full body
 * text as a fallback). Two triggers then re-check for changes:
 *
 * 1. **Visibility** — when the tab regains visibility after being hidden,
 *    an immediate check runs. This catches users returning to a stale tab.
 *
 * 2. **Polling** — a 15-minute interval runs while the tab is visible. This
 *    catches long uninterrupted sessions that span a deploy. The timer is
 *    cleared when the tab is hidden (the visibility check covers that case).
 *
 * Both triggers fetch `index.html` with `cache: "no-store"` and compare the
 * ETag to the baseline. If different, `window.location.reload()` fires.
 * If the fetch fails (offline, network error), nothing happens — we don't
 * reload into an error state.
 *
 * ## Why ETag comparison works
 *
 * - `index.html` is served with `Cache-Control: no-cache, no-store,
 *   must-revalidate`, so the fetch always revalidates with CloudFront.
 * - S3 generates ETags automatically; CloudFront forwards them.
 * - Every Vite production build produces a different `index.html` because the
 *   hashed `<script>` and `<link>` tag filenames change.
 *
 * ## Why it's skipped in dev
 *
 * Vite's dev server may not return stable ETags, and HMR already handles code
 * updates. The `import.meta.env.DEV` guard prevents spurious reloads. Vite
 * tree-shakes this check away in production builds.
 */
import { useEffect, useRef } from "react";

/** How often to poll for a new deploy while the tab is visible. */
const POLL_MS = 15 * 60 * 1000; // 15 minutes

/**
 * Fetch the current ETag (or body text) of index.html.
 *
 * Uses `cache: "no-store"` to bypass the browser HTTP cache entirely,
 * ensuring we always hit CloudFront (which revalidates against S3).
 *
 * Returns null on any failure — the caller treats this as "can't check
 * right now" and skips the reload decision.
 */
async function fetchFingerprint(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return null;

    // Prefer ETag — a single header comparison without reading the body.
    const etag = res.headers.get("etag");
    if (etag) return etag;

    // Fallback: use the full body text. index.html is ~1KB so this is cheap.
    // This covers CDN configurations that strip or don't forward ETags.
    return await res.text();
  } catch {
    // Network error, offline, DNS failure — silently skip.
    return null;
  }
}

/**
 * Compare the current index.html fingerprint against the known baseline.
 * If different, a new deploy has landed — reload the page.
 */
async function checkAndReload(
  url: string,
  knownFingerprint: string,
): Promise<void> {
  const current = await fetchFingerprint(url);

  // Fetch failed — don't reload into an error state.
  if (current === null) return;

  // Fingerprint changed — new deploy has landed.
  if (current !== knownFingerprint) {
    window.location.reload();
  }
}

/**
 * Auto-reload the page when a new production deploy is detected.
 *
 * Mount once at the app root (Layout). Has no render output and causes no
 * re-renders — all state is held in refs.
 */
export function useDeployFreshness(): void {
  // Baseline fingerprint captured on mount.
  const knownFingerprintRef = useRef<string | null>(null);

  // Handle to the visible-tab poll interval, so we can clear it on hide.
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Skip entirely in dev — Vite HMR handles code updates, and the dev
    // server may return unstable ETags causing spurious reloads.
    if (import.meta.env.DEV) return;

    // The URL to check — the SPA entry point served by CloudFront.
    const indexUrl = import.meta.env.BASE_URL || "/";

    // --- Start/stop the poll timer based on tab visibility ---

    function startTimer() {
      if (timerRef.current !== null) return; // already running
      timerRef.current = setInterval(() => {
        if (knownFingerprintRef.current) {
          checkAndReload(indexUrl, knownFingerprintRef.current);
        }
      }, POLL_MS);
    }

    function stopTimer() {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    // --- Visibility change handler ---

    function handleVisibilityChange() {
      if (document.visibilityState === "hidden") {
        // Tab hidden — stop polling. The visibility check on return covers
        // any staleness that accumulates while hidden.
        stopTimer();
        return;
      }

      // Tab became visible — check immediately, then start polling.
      if (knownFingerprintRef.current) {
        checkAndReload(indexUrl, knownFingerprintRef.current);
      }
      startTimer();
    }

    // --- Initialise ---

    // Capture the baseline fingerprint. If this fails (e.g. app loaded
    // while briefly offline), knownFingerprintRef stays null and all
    // subsequent checks are gracefully skipped.
    fetchFingerprint(indexUrl).then((fp) => {
      if (fp) knownFingerprintRef.current = fp;
    });

    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Start the timer if the tab is already visible at mount time.
    if (document.visibilityState === "visible") {
      startTimer();
    }

    // --- Cleanup ---

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      stopTimer();
    };
  }, []);
}
