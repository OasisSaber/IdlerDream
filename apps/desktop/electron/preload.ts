import { contextBridge, ipcRenderer } from "electron";

const api = Object.freeze({
  appInfo: () => ipcRenderer.invoke("idlerdream:app-info"),
  control: (command: string, payload?: Record<string, unknown>) => ipcRenderer.invoke("idlerdream:control", command, payload),
  openFolder: (folderPath: string) => ipcRenderer.invoke("idlerdream:open-folder", folderPath),
});

contextBridge.exposeInMainWorld("idlerdream", api);
