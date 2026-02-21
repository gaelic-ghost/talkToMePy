import os

import uvicorn


def main() -> None:
    host = os.getenv("TALKTOMEPY_HOST", "127.0.0.1")
    port = int(os.getenv("TALKTOMEPY_PORT", "8000"))
    reload_enabled = os.getenv("TALKTOMEPY_RELOAD", "false").strip().lower() == "true"
    uvicorn.run("app.api:app", host=host, port=port, reload=reload_enabled)


if __name__ == "__main__":
    main()
