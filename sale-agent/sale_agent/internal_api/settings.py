from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _apply_env_file(path: Path) -> None:
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def load_env_file(path: str | None = None) -> None:
    """极简 .env 加载器（零依赖）：把 KEY=VALUE 写入 os.environ，不覆盖已有变量。

    值不经过 shell 解析，可安全处理含 & / 空格等特殊字符的值（如 JDBC URL）。
    候选路径依次尝试：显式 path → 当前工作目录 .env → 项目根 .env（基于本模块位置
    推导），找到第一个存在的即加载并返回；全部找不到时静默跳过。
    """
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path))
    candidates.append(Path(".env"))
    candidates.append(Path(__file__).resolve().parents[3] / ".env")
    for candidate in candidates:
        if not candidate.is_file():
            continue
        _apply_env_file(candidate)
        return


@dataclass
class InternalApiSettings:
    host: str = "127.0.0.1"
    port: int = 8000
    token: str = ""
    registry_path: str = str(Path("output") / "internal_api" / "runs.json")


def load_settings() -> InternalApiSettings:
    host = os.environ.get("SALE_INTERNAL_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port_raw = os.environ.get("SALE_INTERNAL_API_PORT", "8000").strip() or "8000"
    token = os.environ.get("SALE_INTERNAL_API_TOKEN", "").strip()
    registry_path = os.environ.get("SALE_INTERNAL_API_REGISTRY", "").strip() or str(Path("output") / "internal_api" / "runs.json")
    try:
        port = int(port_raw)
    except ValueError:
        port = 8000
    return InternalApiSettings(host=host, port=port, token=token, registry_path=registry_path)
