from __future__ import annotations

import uvicorn

from sale_agent.internal_api.settings import load_env_file, load_settings


def main() -> int:
    load_env_file()
    settings = load_settings()
    uvicorn.run("sale_agent.internal_api.app:app", host=settings.host, port=settings.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
