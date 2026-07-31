interface RetryOptions {
  retries?: number;
  baseDelay?: number;
  signal?: AbortSignal;
}

function waitForOnline(signal?: AbortSignal): Promise<void> {
  if (navigator.onLine) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const onOnline = () => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    };
    const onAbort = () => {
      window.removeEventListener("online", onOnline);
      reject(signal!.reason);
    };
    window.addEventListener("online", onOnline, { once: true });
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function fetchWithRetry<T>(
  fn: () => Promise<T>,
  { retries = 3, baseDelay = 1000, signal }: RetryOptions = {},
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      signal?.throwIfAborted();
      return await fn();
    } catch (err: unknown) {
      // Don't retry 4xx client errors
      if (err instanceof Error && "status" in err) {
        const status = (err as Error & { status: number }).status;
        if (status >= 400 && status < 500) throw err;
      }
      if (attempt >= retries) throw err;
      signal?.throwIfAborted();

      await waitForOnline(signal);
      const jitter = Math.random() * 500;
      const delay = baseDelay * 2 ** attempt + jitter;
      await new Promise((r) => setTimeout(r, delay));
    }
  }
}
