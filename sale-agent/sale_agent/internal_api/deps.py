from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sale_agent.internal_api.project_service import ProjectService
from sale_agent.internal_api.service import RunService

bearer = HTTPBearer(auto_error=False)


def get_run_service(request: Request) -> RunService:
    return request.app.state.run_service


def get_project_service(request: Request) -> ProjectService:
    return request.app.state.project_service


def require_internal_auth(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> None:
    expected = getattr(request.app.state, "settings", None)
    token = expected.token if expected is not None else os.environ.get("SALE_INTERNAL_API_TOKEN", "").strip()
    expected = token.strip()
    if not expected:
        return
    actual = credentials.credentials if credentials is not None else ""
    if actual != expected:
        raise HTTPException(status_code=401, detail="unauthorized")
