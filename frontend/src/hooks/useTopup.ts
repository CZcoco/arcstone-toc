import { useEffect, useCallback } from "react";
import { BASE_URL } from "@/lib/api";

/** Fallback topup URL when backend is unreachable */
function getFallbackTopupUrl(): string {
  const base = (
    localStorage.getItem("econ-agent-new-api-url") ||
    "http://43.128.44.82:3000"
  ).replace(/\/v1$/, "");
  return `${base}/topup`;
}

export function useTopup(onBalanceRefresh: () => void) {
  // Listen for topup window close (Electron only)
  useEffect(() => {
    if (!window.electronAPI) return;
    return window.electronAPI.onTopupClosed(() => {
      onBalanceRefresh();
    });
  }, [onBalanceRefresh]);

  const openTopup = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}/auth/topup-context`);
      const data = await res.json();
      if (!data.ok) {
        window.open(getFallbackTopupUrl(), "_blank");
        return;
      }

      if (window.electronAPI) {
        // Electron: open in-app window with session cookie
        await window.electronAPI.openTopup(
          data.url,
          data.session_cookie,
          data.domain
        );
      } else {
        // Web fallback
        window.open(data.url, "_blank");
        const onFocus = () => {
          onBalanceRefresh();
          window.removeEventListener("focus", onFocus);
        };
        window.addEventListener("focus", onFocus);
      }
    } catch {
      window.open(getFallbackTopupUrl(), "_blank");
    }
  }, [onBalanceRefresh]);

  return { openTopup };
}
