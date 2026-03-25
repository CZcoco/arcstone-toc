const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  openTopup: (url, sessionCookie, domain) =>
    ipcRenderer.invoke("open-topup", url, sessionCookie, domain),
  onTopupClosed: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("topup-closed", handler);
    return () => ipcRenderer.removeListener("topup-closed", handler);
  },
  isElectron: true,
});
