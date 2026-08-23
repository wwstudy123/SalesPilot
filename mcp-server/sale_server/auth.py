"""JWT 身份闸门（权限四闸门之一）：HS256 共享密钥校验，与 business-mock 同一密钥。

不引第三方 JWT 库：标准库 hmac/hashlib 足够（MVP 仅校验签名与过期）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

DEFAULT_SECRET = "sale-dev-jwt-secret-please-change-me-0123456789"


@dataclass
class Identity:
    employee_id: int
    username: str
    name: str
    role: str  # employee / manager

    @property
    def is_manager(self) -> bool:
        return self.role == "manager"


def _jwt_secret() -> str:
    return os.environ.get("SALE_JWT_SECRET", DEFAULT_SECRET).strip() or DEFAULT_SECRET


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def verify_jwt(token: str) -> Identity | None:
    """校验 HS256 签名与 exp；失败返回 None（网关回 401 E_UNAUTHORIZED）。"""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = hmac.new(_jwt_secret().encode(), signing_input, hashlib.sha256).digest()
    try:
        actual = _b64url_decode(signature_b64)
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(expected, actual):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, TypeError):
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time():
        return None
    try:
        return Identity(
            employee_id=int(payload["eid"]),
            username=str(payload.get("sub", "")),
            name=str(payload.get("name", "")),
            role=str(payload.get("role", "")),
        )
    except (KeyError, ValueError, TypeError):
        return None
