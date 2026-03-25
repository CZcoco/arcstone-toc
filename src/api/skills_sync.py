"""
云端技能同步 — 启动时从 VPS 拉取最新技能包，解压到本地 SKILLS_DIR。
用户无需手动管理技能文件。
"""

import fnmatch
import hashlib
import io
import logging
import os
import shutil
import tarfile

import httpx

logger = logging.getLogger(__name__)


def _config_base() -> str:
    base = os.environ.get("NEW_API_URL", "http://43.128.44.82:3000/v1")
    return base.removesuffix("/v1").removesuffix("/")


def _version_url() -> str:
    return f"{_config_base()}/config/skills-version.json"


def _bundle_url() -> str:
    return f"{_config_base()}/config/skills.tar.gz"


def _local_version_path(skills_dir: str) -> str:
    return os.path.join(skills_dir, ".cloud-version")


USER_CONFIG_PATTERNS = ["*_config.json", "*.local.json", "*.local.*"]


def _collect_user_configs(skills_dir: str) -> dict[str, bytes]:
    """扫描并备份用户配置文件（相对路径 → 内容）。"""
    configs: dict[str, bytes] = {}
    for root, _, files in os.walk(skills_dir):
        for f in files:
            if any(fnmatch.fnmatch(f, pat) for pat in USER_CONFIG_PATTERNS):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, skills_dir)
                try:
                    with open(full, "rb") as fh:
                        configs[rel] = fh.read()
                except OSError:
                    pass
    return configs


def _restore_user_configs(skills_dir: str, configs: dict[str, bytes]) -> None:
    """将备份的用户配置文件写回。"""
    for rel_path, content in configs.items():
        target = os.path.join(skills_dir, rel_path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(content)
        logger.info("恢复用户配置: %s", rel_path)


def sync_skills(skills_dir: str) -> None:
    """从 VPS 同步技能。启动时在后台线程调用。

    流程：
    1. 获取远程版本号
    2. 与本地版本比较
    3. 版本不同则下载 tar.gz 并解压覆盖
    """
    try:
        # 获取远程版本
        resp = httpx.get(_version_url(), timeout=10)
        resp.raise_for_status()
        remote_data = resp.json()
        remote_version = remote_data.get("version", "")
        if not remote_version:
            logger.debug("远程技能版本为空，跳过同步")
            return

        # 检查本地版本
        ver_path = _local_version_path(skills_dir)
        local_version = ""
        if os.path.exists(ver_path):
            with open(ver_path, "r") as f:
                local_version = f.read().strip()

        if local_version == remote_version:
            logger.info("技能已是最新版本 (%s)", remote_version)
            return

        # 下载技能包
        logger.info("下载技能包 (本地=%s, 远程=%s)...", local_version or "无", remote_version)
        bundle_resp = httpx.get(_bundle_url(), timeout=60)
        bundle_resp.raise_for_status()

        # 解压到临时目录，再替换
        os.makedirs(skills_dir, exist_ok=True)
        tmp_dir = skills_dir + ".tmp"
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir)

        try:
            with tarfile.open(fileobj=io.BytesIO(bundle_resp.content), mode="r:gz") as tar:
                # 安全检查：防止路径穿越
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in member.name:
                        logger.warning("跳过不安全路径: %s", member.name)
                        continue
                    tar.extract(member, tmp_dir)

            # 备份用户本地配置（如 stata_config.json）
            user_configs = _collect_user_configs(skills_dir)

            # 清空旧技能目录中的云端内容，保留 .cloud-version
            for item in os.listdir(skills_dir):
                if item == ".cloud-version":
                    continue
                item_path = os.path.join(skills_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

            # 移动新内容
            for item in os.listdir(tmp_dir):
                src = os.path.join(tmp_dir, item)
                dst = os.path.join(skills_dir, item)
                shutil.move(src, dst)

            # 恢复用户配置
            if user_configs:
                _restore_user_configs(skills_dir, user_configs)

            # 写入版本号
            with open(ver_path, "w") as f:
                f.write(remote_version)

            logger.info("技能已更新到版本 %s", remote_version)

        finally:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)

    except Exception as e:
        logger.warning("技能同步失败: %s（将使用本地已有技能）", e)
