from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="sale-mcp-server", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {
        "service": "mcp-server",
        "status": "UP",
        "time": datetime.now(timezone.utc).isoformat(),
    }
