import { useState, useEffect, useCallback } from "react";
import {
  quickStart,
  getUserInfo,
  logout as apiLogout,
  type UserInfo,
} from "@/lib/auth";

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // 启动时检查是否已登录（后端自动用 saved credentials 重登录）
  useEffect(() => {
    getUserInfo()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  /** 一步到位：自动注册+登录 */
  const start = useCallback(async (username: string, password: string) => {
    const { user } = await quickStart(username, password);
    setUser(user);
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const refreshBalance = useCallback(async () => {
    const info = await getUserInfo(true);
    if (info) setUser(info);
  }, []);

  return { user, loading, start, logout, refreshBalance };
}
