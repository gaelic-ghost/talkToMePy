from __future__ import annotations

from pathlib import Path
import os
import sys

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api import app


def main() -> None:
    output_path = Path(
        os.getenv(
            "OPENAPI_EXPORT_PATH",
            str(ROOT_DIR / "openapi" / "openapi.generated.yaml"),
        )
    )
    if not output_path.is_absolute():
        output_path = ROOT_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()
    with output_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(schema, f, sort_keys=False)

    print(f"Wrote OpenAPI spec: {output_path}")


if __name__ == "__main__":
    main()
