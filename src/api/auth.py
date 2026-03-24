"""用户认证服务 - 封装 New API 的注册/登录/用户信息接口

认证模型：
- 首次使用：用户输入用户名+密码 → 自动注册+登录 → 凭证存本地
- 再次启动：用saved credentials自动登录，用户无感
- LLM 调用：共享系统 token（ECON_USER_TOKEN，admin 预设）
- 用户管理：session cookie + New-Api-User header
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)


def _base_url() -> str:
    """New API 根地址（不带 /v1）"""
    url = os.environ.get("NEW_API_URL", "http://43.128.44.82:3000/v1")
    return url.removesuffix("/v1").removesuffix("/")


def _safe_json(resp: httpx.Response) -> dict:
    """安全解析 JSON 响应，空 body 返回失败 dict"""
    if not resp.content:
        return {"success": False, "message": f"服务端返回空响应 (HTTP {resp.status_code})"}
    try:
        return resp.json()
    except Exception:
        return {"success": False, "message": f"服务端返回异常 (HTTP {resp.status_code})"}


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def quick_start(username: str, password: str) -> dict:
    """一步到位：自动注册（如果不存在）+ 登录

    这是面向用户的唯一入口。用户只需输入用户名和密码，
    后台静默处理注册/登录，永远不会看到"用户已存在"之类的错误。
    """
    base = _base_url()

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        # 先尝试登录
        login_resp = client.post(
            f"{base}/api/user/login",
            json={"username": username, "password": password},
        )
        if login_resp.status_code == 429:
            raise AuthError("请求过于频繁，请稍后再试", 429)

        login_data = _safe_json(login_resp)

        # 登录失败 → 可能是新用户，尝试注册
        if not login_data.get("success"):
            reg_resp = client.post(
                f"{base}/api/user/register",
                json={"username": username, "password": password},
                timeout=15,
            )
            if reg_resp.status_code == 429:
                raise AuthError("请求过于频繁，请稍后再试", 429)

            reg_data = _safe_json(reg_resp)
            if not reg_data.get("success"):
                msg = reg_data.get("message", "")
                if "已存在" in msg or "exist" in msg.lower():
                    raise AuthError("密码错误，请重试")
                raise AuthError(msg or "登录失败，请检查用户名和密码")

            # 注册成功，再次登录（加延迟避免限流）
            import time
            time.sleep(1)
            login_resp = client.post(
                f"{base}/api/user/login",
                json={"username": username, "password": password},
            )
            if login_resp.status_code == 429:
                raise AuthError("请求过于频繁，请稍后再试", 429)
            login_data = _safe_json(login_resp)
            if not login_data.get("success"):
                raise AuthError("注册成功但登录失败，请重试")

        # 登录成功，提取信息
        user_data = login_data.get("data", {})
        user_id = user_data.get("id")
        session_cookie = client.cookies.get("session", "")

        if not session_cookie or not user_id:
            raise AuthError("登录异常，请重试")

        # 获取完整用户信息
        headers = {"New-Api-User": str(user_id)}
        user_info = user_data  # login 已返回基本信息
        try:
            user_resp = client.get(f"{base}/api/user/self", headers=headers)
            if user_resp.status_code == 200:
                ud = user_resp.json()
                if ud.get("success"):
                    user_info = ud.get("data", user_data)
        except Exception:
            pass  # 用 login 返回的基本信息就够了

    return {
        "session_cookie": session_cookie,
        "user_id": user_id,
        "user": {
            "username": user_info.get("username", username),
            "display_name": user_info.get("display_name", username),
            "quota": user_info.get("quota", 0),
            "used_quota": user_info.get("used_quota", 0),
            "group": user_info.get("group", "default"),
        },
    }


def get_user_info(session_cookie: str, user_id: int) -> dict:
    """查询用户信息（余额、用量等）"""
    base = _base_url()
    resp = httpx.get(
        f"{base}/api/user/self",
        cookies={"session": session_cookie},
        headers={"New-Api-User": str(user_id)},
        timeout=10,
    )
    if resp.status_code == 401:
        raise AuthError("会话已过期，请重新登录", 401)
    data = _safe_json(resp)
    if not data.get("success"):
        raise AuthError(data.get("message", "获取用户信息失败"), 401)
    user = data.get("data", {})
    return {
        "username": user.get("username", ""),
        "display_name": user.get("display_name", ""),
        "quota": user.get("quota", 0),
        "used_quota": user.get("used_quota", 0),
        "group": user.get("group", "default"),
    }


def auto_login(username: str, password: str) -> dict | None:
    """用保存的凭证自动登录，失败返回 None（不抛异常）"""
    try:
        return quick_start(username, password)
    except Exception:
        return None
