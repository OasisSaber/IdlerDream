/// <reference types="vite/client" />

declare global {
  interface Window {
    idlerdream?: {
      appInfo(): Promise<{ version: string; apiBaseUrl: string; profile: string; readToken: string }>;
      control(command: string, payload?: Record<string, unknown>): Promise<unknown>;
      openFolder(path: string): Promise<string>;
      pickDirectory(): Promise<string | null>;
    };
  }
}
export {};
