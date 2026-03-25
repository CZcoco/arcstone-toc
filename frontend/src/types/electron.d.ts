interface ElectronAPI {
  openTopup: (url: string, sessionCookie: string, domain: string) => Promise<void>;
  onTopupClosed: (callback: () => void) => () => void;
  isElectron: true;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
