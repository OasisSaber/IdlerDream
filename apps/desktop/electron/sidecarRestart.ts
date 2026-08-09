/**
 * Bounded Sidecar restart gate (CR-24 / CR-06).
 *
 * A persistent Sidecar startup failure must not turn into an unbounded restart
 * loop. The gate allows at most `maxAttempts` restarts inside a rolling
 * `windowMs`, mirroring the behaviour the renderer used to observe as an
 * endless crash cycle.
 */
export interface RestartGate {
  /** Record an attempt now and report whether another restart is allowed. */
  mayRestart(now?: number): boolean;
  /** Forget all recorded attempts (used in tests and on explicit user retry). */
  reset(): void;
}

export function createRestartGate(
  maxAttempts = 3,
  windowMs = 60_000,
): RestartGate {
  const attempts: number[] = [];
  return {
    mayRestart(now = Date.now()): boolean {
      while (attempts.length && now - attempts[0] > windowMs) {
        attempts.shift();
      }
      if (attempts.length >= maxAttempts) {
        return false;
      }
      attempts.push(now);
      return true;
    },
    reset(): void {
      attempts.length = 0;
    },
  };
}
