from __future__ import annotations

import uvicorn


def main() -> int:
    uvicorn.run("sale_server.app:app", host="127.0.0.1", port=9010, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
