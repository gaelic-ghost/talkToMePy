from __future__ import annotations

from pathlib import Path
import difflib

import yaml


def test_target_openapi_matches_generated_openapi() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    target_path = repo_root / "openapi" / "openapi.yaml"
    generated_path = repo_root / "openapi" / "openapi.generated.yaml"

    assert generated_path.exists(), (
        "Missing generated OpenAPI file: openapi/openapi.generated.yaml. "
        "Run `uv run python scripts/export_openapi.py` before tests."
    )

    target_spec = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    generated_spec = yaml.safe_load(generated_path.read_text(encoding="utf-8"))

    if target_spec != generated_spec:
        target_dump = yaml.safe_dump(target_spec, sort_keys=True).splitlines(keepends=True)
        generated_dump = yaml.safe_dump(generated_spec, sort_keys=True).splitlines(keepends=True)
        diff = "".join(
            difflib.unified_diff(
                target_dump,
                generated_dump,
                fromfile=str(target_path),
                tofile=str(generated_path),
            )
        )
        raise AssertionError(
            "OpenAPI parity failed: target spec differs from generated spec.\n"
            "Re-export with `uv run python scripts/export_openapi.py` and either:\n"
            "1) update runtime/models to match target, or\n"
            "2) intentionally revise target spec in the same change.\n\n"
            f"{diff}"
        )
