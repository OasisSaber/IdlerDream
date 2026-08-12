import { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, nativeTheme, shell, Tray } from "electron";
import type { ChildProcess } from "node:child_process";
import { spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRestartGate } from "./sidecarRestart.js";

const sidecarRestartGate = createRestartGate(3, 60_000);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API_PORT = 38173;
const CONTROL_PORT = 38174;
const PROFILE = process.env.IDLERDREAM_PROFILE ?? "default";
const CONTROL_TOKEN = crypto.randomBytes(32).toString("hex");
const READ_TOKEN = crypto.randomBytes(32).toString("hex");
const CONTROL_PIPE = `\\\\.\\pipe\\IdlerDream-${PROFILE}`;
const CONTROL_COMMANDS = new Set([
  "ping", "project.add", "project.discover", "project.remove",
  "project.restore", "project.purge", "project.list_removed",
  "inspection.start", "inspection.cancel",
  // CR-15: Onboarding/Settings functional flows.
  "inspector.status", "inspector.config.get", "inspector.config.update",
  "inspector.credential.set", "inspector.credential.delete",
  "inspector.connectivity.test", "inspector.compatibility.test",
]);

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let sidecar: ChildProcess | null = null;
let isQuitting = false;

function sidecarExecutable(): string {
  if (!app.isPackaged) return process.env.IDLERDREAM_PYTHON ?? "python";
  return path.join(process.resourcesPath, "sidecar", "idlerdream-sidecar.exe");
}

function sidecarArgs(): string[] {
  return app.isPackaged ? [] : ["-m", "idlerdream.main"];
}

function mayRestartSidecar(): boolean {
  return sidecarRestartGate.mayRestart();
}

function spawnSidecar(): void {
  if (process.env.IDLERDREAM_SKIP_SIDECAR === "1" || sidecar) return;
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    IDLERDREAM_PROFILE: PROFILE,
    IDLERDREAM_API_PORT: String(API_PORT),
    IDLERDREAM_CONTROL_PORT: String(CONTROL_PORT),
    IDLERDREAM_CONTROL_TOKEN: CONTROL_TOKEN,
    IDLERDREAM_READ_TOKEN: READ_TOKEN,
  };
  if (!app.isPackaged) env.PYTHONPATH = path.resolve(__dirname, "../../sidecar");

  sidecar = spawn(sidecarExecutable(), sidecarArgs(), {
    env,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  sidecar.stdout?.on("data", (chunk) => console.info(`[sidecar] ${String(chunk).trim()}`));
  sidecar.stderr?.on("data", (chunk) => console.error(`[sidecar] ${String(chunk).trim()}`));
  sidecar.once("exit", (code) => {
    sidecar = null;
    if (!isQuitting && code !== 0 && mayRestartSidecar()) setTimeout(spawnSidecar, 2500);
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 940,
    minWidth: 1100,
    minHeight: 720,
    show: false,
    backgroundColor: nativeTheme.shouldUseDarkColors ? "#111216" : "#f3f4f7",
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#00000000",
      symbolColor: nativeTheme.shouldUseDarkColors ? "#f5f5f7" : "#1d1d1f",
      height: 52,
    },
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.once("ready-to-show", () => mainWindow?.show());
  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) void mainWindow.loadURL(devUrl);
  else void mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
}

function createTray(): void {
  const iconPath = path.join(app.getAppPath(), "resources", "tray.png");
  const icon = fs.existsSync(iconPath) ? nativeImage.createFromPath(iconPath) : nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setToolTip("IdlerDream");
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "打开 IdlerDream", click: () => { mainWindow?.show(); mainWindow?.focus(); } },
    { type: "separator" },
    { label: "完全退出", click: () => { isQuitting = true; app.quit(); } },
  ]));
  tray.on("double-click", () => { mainWindow?.show(); mainWindow?.focus(); });
}

function sendControl(command: string, payload: Record<string, unknown> = {}): Promise<unknown> {
  if (!CONTROL_COMMANDS.has(command)) return Promise.reject(new Error(`Unsupported control command: ${command}`));
  return new Promise((resolve, reject) => {
    const socket = process.platform === "win32"
      ? net.createConnection(CONTROL_PIPE)
      : net.createConnection({ host: "127.0.0.1", port: CONTROL_PORT });
    let response = "";
    let settled = false;
    const finish = (error?: Error, value?: unknown) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      error ? reject(error) : resolve(value);
    };
    const timeout = setTimeout(() => { socket.destroy(); finish(new Error("Sidecar control timeout")); }, 30_000);
    socket.setEncoding("utf8");
    socket.once("connect", () => socket.write(`${JSON.stringify({ token: CONTROL_TOKEN, command, payload })}\n`));
    socket.on("data", (chunk) => { response += chunk; if (response.includes("\n")) socket.end(); });
    socket.once("error", (error) => finish(error));
    socket.once("close", () => {
      try {
        const parsed = JSON.parse(response.trim());
        if (!parsed.ok) finish(new Error(parsed.error ?? "Control request failed"));
        else finish(undefined, parsed.result);
      } catch (error) {
        finish(error instanceof Error ? error : new Error(String(error)));
      }
    });
  });
}

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", () => { mainWindow?.show(); mainWindow?.focus(); });
  app.whenReady().then(() => {
    spawnSidecar();
    createWindow();
    createTray();

    ipcMain.handle("idlerdream:control", (_event, command: unknown, payload?: unknown) => {
      if (typeof command !== "string" || (payload !== undefined && (typeof payload !== "object" || payload === null || Array.isArray(payload)))) {
        throw new TypeError("Invalid control request");
      }
      return sendControl(command, (payload ?? {}) as Record<string, unknown>);
    });
    ipcMain.handle("idlerdream:open-folder", async (_event, folderPath: unknown) => {
      if (typeof folderPath !== "string" || !path.isAbsolute(folderPath) || !fs.existsSync(folderPath)) {
        throw new Error("Workspace path is invalid or missing");
      }
      const error = await shell.openPath(folderPath);
      if (error) throw new Error(error);
      return "";
    });
    ipcMain.handle("idlerdream:pick-directory", async (event) => {
      const parent = BrowserWindow.fromWebContents(event.sender);
      const options: Electron.OpenDialogOptions = {
        title: "选择要监控的工作区目录",
        properties: ["openDirectory", "createDirectory"],
      };
      const result = parent
        ? await dialog.showOpenDialog(parent, options)
        : await dialog.showOpenDialog(options);
      if (result.canceled || !result.filePaths.length) return null;
      return result.filePaths[0];
    });
    ipcMain.handle("idlerdream:app-info", () => ({
      version: app.getVersion(),
      apiBaseUrl: `http://127.0.0.1:${API_PORT}`,
      profile: PROFILE,
      readToken: READ_TOKEN,
    }));

    app.on("activate", () => { if (!mainWindow) createWindow(); else mainWindow.show(); });
  });
}

app.on("before-quit", () => {
  isQuitting = true;
  sidecar?.kill();
});
app.on("window-all-closed", () => { /* Keep the tray process alive. */ });
