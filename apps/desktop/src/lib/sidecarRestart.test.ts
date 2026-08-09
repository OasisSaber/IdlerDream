import { describe, expect, it } from "vitest";

import { createRestartGate } from "./sidecarRestart";

describe("createRestartGate (CR-24 Sidecar crash recovery)", () => {
  it("allows up to maxAttempts restarts inside the window", () => {
    const gate = createRestartGate(3, 60_000);
    expect(gate.mayRestart(1_000)).toBe(true);
    expect(gate.mayRestart(2_000)).toBe(true);
    expect(gate.mayRestart(3_000)).toBe(true);
    expect(gate.mayRestart(4_000)).toBe(false);
  });

  it("forgets attempts older than the rolling window", () => {
    const gate = createRestartGate(2, 60_000);
    expect(gate.mayRestart(1_000)).toBe(true);
    expect(gate.mayRestart(2_000)).toBe(true);
    expect(gate.mayRestart(3_000)).toBe(false);
    // 61 s later the first two attempts have expired.
    expect(gate.mayRestart(61_001)).toBe(true);
    expect(gate.mayRestart(62_001)).toBe(true);
  });

  it("reset clears all recorded attempts", () => {
    const gate = createRestartGate(1, 60_000);
    expect(gate.mayRestart(1_000)).toBe(true);
    expect(gate.mayRestart(2_000)).toBe(false);
    gate.reset();
    expect(gate.mayRestart(3_000)).toBe(true);
  });
});
