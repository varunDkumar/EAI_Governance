import { useEffect } from "react";

/**
 * Runs an async effect (typically one or more `api.get(...).then(setState)`
 * calls) and keeps retrying on failure instead of giving up after one
 * attempt. Every page that fetches on mount needs this: the backend (especially
 * the packaged app's bundled sidecar, which takes 10-40s to cold-start) may
 * not be reachable yet the instant a page first renders, and a one-shot fetch
 * would otherwise leave that page permanently stuck empty/"unreachable" even
 * after the backend becomes healthy seconds later.
 */
export function useRetryingEffect(fn: () => Promise<unknown>, deps: React.DependencyList, options?: { intervalMs?: number; maxAttempts?: number }) {
  const intervalMs = options?.intervalMs ?? 2000;
  const maxAttempts = options?.maxAttempts ?? 60; // ~2 minutes

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let attempts = 0;

    const attempt = () => {
      fn().catch(() => {
        if (cancelled) return;
        attempts += 1;
        if (attempts >= maxAttempts) return;
        timer = window.setTimeout(attempt, intervalMs);
      });
    };

    attempt();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
