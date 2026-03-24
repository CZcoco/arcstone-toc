import { BASE_URL } from "./api";

export interface UserInfo {
  username: string;
  display_name: string;
  quota: number;
  used_quota: number;
  group: string;
}

/** 一步到位：自动注册（新用户）+ 登录 */
export async function quickStart(
  username: string,
  password: string
): Promise<{ user: UserInfo }> {
  const res = await fetch(`${BASE_URL}/auth/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.message || "登录失败");
  return data;
}

/** 获取当前用户信息（后端自动处理 session 过期重登录） */
export async function getUserInfo(): Promise<UserInfo | null> {
  try {
    const res = await fetch(`${BASE_URL}/auth/user`);
    if (res.status === 401) return null;
    const data = await res.json();
    if (!data.ok) return null;
    return data.user;
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await fetch(`${BASE_URL}/auth/logout`, { method: "POST" });
}
