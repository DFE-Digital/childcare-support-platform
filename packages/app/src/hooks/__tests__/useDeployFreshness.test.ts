import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/** Simulate a visibilitychange event with the given state. */
function setVisibility(state: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", {
    value: state,
    writable: true,
    configurable: true,
  });
  document.dispatchEvent(new Event("visibilitychange"));
}

/** Build a minimal Response with an optional ETag header and body text. */
function mockResponse(body: string, etag?: string): Response {
  const headers = new Headers();
  if (etag) headers.set("etag", etag);
  return {
    ok: true,
    headers,
    text: () => Promise.resolve(body),
  } as unknown as Response;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

let fetchMock: ReturnType<typeof vi.fn>;
let reloadMock: ReturnType<typeof vi.fn>;
let unmountHook: (() => void) | null = null;

beforeEach(() => {
  vi.useFakeTimers();

  // Reset module registry so each test gets a fresh import of the hook
  // (prevents closure state from leaking between tests).
  vi.resetModules();

  // Stub import.meta.env for production mode.
  vi.stubEnv("DEV", false);
  // BASE_URL defaults to "/" in Vite — match that.
  vi.stubEnv("BASE_URL", "/");

  // Mock fetch globally.
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  // Mock window.location.reload — jsdom doesn't support it natively.
  reloadMock = vi.fn();
  Object.defineProperty(window, "location", {
    value: { ...window.location, reload: reloadMock },
    writable: true,
    configurable: true,
  });

  // Start with tab visible (normal state).
  Object.defineProperty(document, "visibilityState", {
    value: "visible",
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  // Unmount before restoring timers — ensures the hook's cleanup runs
  // (removing listeners and clearing intervals) while fake timers are
  // still active. Without this, listeners leak between tests.
  if (unmountHook) {
    unmountHook();
    unmountHook = null;
  }
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** Fresh import + render, capturing unmount for afterEach cleanup. */
async function mountHook() {
  const mod = await import("../useDeployFreshness");
  const { unmount } = renderHook(() => mod.useDeployFreshness());
  unmountHook = unmount;
}

// ---------------------------------------------------------------------------
// Visibility trigger
// ---------------------------------------------------------------------------

describe("visibility trigger", () => {
  it("reloads when ETag changes on visibility regain", async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse("<html>v1</html>", '"etag-v1"'))
      .mockResolvedValueOnce(mockResponse("<html>v2</html>", '"etag-v2"'));

    await mountHook();

    // Let the seed fetch resolve.
    await vi.advanceTimersByTimeAsync(0);

    // Hide then show the tab.
    setVisibility("hidden");
    setVisibility("visible");

    // Let the check fetch resolve.
    await vi.advanceTimersByTimeAsync(0);

    expect(reloadMock).toHaveBeenCalledOnce();
  });

  it("does not reload when ETag is unchanged on visibility regain", async () => {
    fetchMock.mockResolvedValue(mockResponse("<html>v1</html>", '"etag-v1"'));

    await mountHook();
    await vi.advanceTimersByTimeAsync(0);

    setVisibility("hidden");
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);

    expect(reloadMock).not.toHaveBeenCalled();
  });

  it("does not reload when fetch fails on visibility check", async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse("<html>v1</html>", '"etag-v1"'))
      .mockRejectedValueOnce(new Error("offline"));

    await mountHook();
    await vi.advanceTimersByTimeAsync(0);

    setVisibility("hidden");
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);

    expect(reloadMock).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Timer trigger
// ---------------------------------------------------------------------------

describe("timer trigger", () => {
  it("reloads when ETag changes after 15-min timer fires", async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse("<html>v1</html>", '"etag-v1"'))
      .mockResolvedValueOnce(mockResponse("<html>v2</html>", '"etag-v2"'));

    await mountHook();
    await vi.advanceTimersByTimeAsync(0);

    // Advance past the 15-minute poll interval.
    await vi.advanceTimersByTimeAsync(15 * 60 * 1000);

    expect(reloadMock).toHaveBeenCalledOnce();
  });

  it("does not reload when ETag is unchanged after timer fires", async () => {
    fetchMock.mockResolvedValue(mockResponse("<html>v1</html>", '"etag-v1"'));

    await mountHook();
    await vi.advanceTimersByTimeAsync(0);

    await vi.advanceTimersByTimeAsync(15 * 60 * 1000);

    expect(reloadMock).not.toHaveBeenCalled();
  });

  it("timer does not fire while tab is hidden", async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse("<html>v1</html>", '"etag-v1"'))
      .mockResolvedValueOnce(mockResponse("<html>v2</html>", '"etag-v2"'));

    await mountHook();
    await vi.advanceTimersByTimeAsync(0);

    // Hide the tab, then advance past the poll interval.
    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(15 * 60 * 1000);

    // fetch should only have been called once (the seed).
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(reloadMock).not.toHaveBeenCalled();
  });

  it("timer restarts when tab becomes visible again", async () => {
    fetchMock.mockResolvedValue(mockResponse("<html>v1</html>", '"etag-v1"'));

    await mountHook();
    await vi.advanceTimersByTimeAsync(0);

    // Hide, advance 10 min (timer should have been cleared), then show.
    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(10 * 60 * 1000);

    // No fetches should have occurred while hidden (besides the initial seed).
    expect(fetchMock).toHaveBeenCalledTimes(1); // only seed

    // Show tab — visibility check fires an immediate fetch, timer restarts.
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);

    const fetchCountAfterVisible = fetchMock.mock.calls.length;

    // Advance the full 15 min — timer should fire one more fetch.
    await vi.advanceTimersByTimeAsync(15 * 60 * 1000);
    expect(fetchMock.mock.calls.length).toBe(fetchCountAfterVisible + 1);
  });
});

// ---------------------------------------------------------------------------
// General
// ---------------------------------------------------------------------------

describe("general", () => {
  it("does not reload when initial seed fetch fails", async () => {
    fetchMock
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(mockResponse("<html>v2</html>", '"etag-v2"'));

    await mountHook();
    await vi.advanceTimersByTimeAsync(0);

    // Visibility cycle — should be skipped because no baseline exists.
    setVisibility("hidden");
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);

    expect(reloadMock).not.toHaveBeenCalled();
  });

  it("falls back to body comparison when ETag header is absent", async () => {
    // No ETag in headers — fetchFingerprint should use body text.
    fetchMock
      .mockResolvedValueOnce(mockResponse("<html>v1</html>"))
      .mockResolvedValueOnce(mockResponse("<html>v2</html>"));

    await mountHook();
    await vi.advanceTimersByTimeAsync(0);

    setVisibility("hidden");
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);

    expect(reloadMock).toHaveBeenCalledOnce();
  });

  it("cleans up listener and timer on unmount", async () => {
    fetchMock.mockResolvedValue(mockResponse("<html>v1</html>", '"etag-v1"'));

    const removeSpy = vi.spyOn(document, "removeEventListener");

    await mountHook();
    await vi.advanceTimersByTimeAsync(0);

    // Explicitly unmount (also clears the afterEach reference).
    unmountHook!();
    unmountHook = null;

    expect(removeSpy).toHaveBeenCalledWith(
      "visibilitychange",
      expect.any(Function),
    );

    // After unmount, advancing timers should not trigger any more fetches.
    const fetchCountAtUnmount = fetchMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(15 * 60 * 1000);
    expect(fetchMock.mock.calls.length).toBe(fetchCountAtUnmount);
  });
});
