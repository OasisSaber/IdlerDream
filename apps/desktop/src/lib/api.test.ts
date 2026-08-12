import { afterEach, describe, expect, it, vi } from "vitest";
import {
  deleteInspectorCredential,
  fetchInspectorConfig,
  fetchInspectorStatus,
  setInspectorCredential,
  testInspectorCompatibility,
  testInspectorConnectivity,
  updateInspectorConfig,
} from "./api";

/** CR-15: the renderer must route the typed inspector operations to the
 * Electron control bridge with the exact command names the Sidecar serves. */

const control = vi.fn(async (_command: string, _payload?: Record<string, unknown>) => ({}));

function stubBridge() {
  Object.defineProperty(window, "idlerdream", {
    configurable: true,
    value: {
      appInfo: vi.fn(async () => ({ version: "0.1.0", apiBaseUrl: "http://127.0.0.1:38173", profile: "test", readToken: "tok" })),
      control,
      openFolder: vi.fn(),
      pickDirectory: vi.fn(),
    },
  });
}

afterEach(() => {
  control.mockClear();
  delete (window as unknown as Record<string, unknown>).idlerdream;
});

describe("inspector control commands", () => {
  it("routes status and config reads", async () => {
    stubBridge();
    await fetchInspectorStatus();
    expect(control).toHaveBeenCalledWith("inspector.status", {});
    await fetchInspectorConfig();
    expect(control).toHaveBeenCalledWith("inspector.config.get", {});
  });

  it("routes config updates without extra payload keys", async () => {
    stubBridge();
    await updateInspectorConfig({ provider: "deepseek", model: "deepseek/v4", base_url: "https://api.example.com/v1" });
    expect(control).toHaveBeenCalledWith("inspector.config.update", {
      provider: "deepseek",
      model: "deepseek/v4",
      base_url: "https://api.example.com/v1",
    });
  });

  it("routes credential set/delete with snake_case payloads", async () => {
    stubBridge();
    await setInspectorCredential("deepseek", "sk-secret");
    expect(control).toHaveBeenCalledWith("inspector.credential.set", { provider: "deepseek", api_key: "sk-secret" });
    await deleteInspectorCredential("deepseek");
    expect(control).toHaveBeenCalledWith("inspector.credential.delete", { provider: "deepseek" });
  });

  it("routes connectivity test with the optional api key and compatibility test", async () => {
    stubBridge();
    await testInspectorConnectivity("deepseek", "https://api.example.com/v1", "deepseek/v4", "sk-live");
    expect(control).toHaveBeenCalledWith("inspector.connectivity.test", {
      provider: "deepseek",
      base_url: "https://api.example.com/v1",
      model: "deepseek/v4",
      api_key: "sk-live",
    });
    await testInspectorConnectivity("deepseek", "https://api.example.com/v1", "deepseek/v4");
    expect(control).toHaveBeenCalledWith("inspector.connectivity.test", {
      provider: "deepseek",
      base_url: "https://api.example.com/v1",
      model: "deepseek/v4",
      api_key: "",
    });
    await testInspectorCompatibility();
    expect(control).toHaveBeenCalledWith("inspector.compatibility.test", {});
  });
});
