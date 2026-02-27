from __future__ import annotations

import argparse
from pathlib import Path
import sys

from smoke_common import assert_wav_response, ensure_healthy, load_mode_and_wait, request_binary, request_json


DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run API e2e smoke test for custom voice synthesis.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="TalkToMePy service base URL.")
    parser.add_argument("--model-id", default=DEFAULT_MODEL, help="Custom voice model id.")
    parser.add_argument("--speaker", default="", help="Optional explicit speaker override.")
    parser.add_argument("--text", default="Hello from custom voice smoke test.", help="Text to synthesize.")
    parser.add_argument("--language", default="English", help="Language to synthesize.")
    parser.add_argument("--output", default="outputs/custom_voice_smoke.wav", help="Output WAV file path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        ensure_healthy(args.base_url)
        load_mode_and_wait(args.base_url, mode="custom_voice")

        status, _, payload = request_json(
            "GET",
            f"{args.base_url}/custom-voice/speakers?model_id={args.model_id}",
            timeout=60.0,
        )
        if status != 200 or not isinstance(payload, dict):
            raise RuntimeError(f"/custom-voice/speakers failed status={status} payload={payload}")

        speakers = payload.get("speakers") or []
        selected_speaker = args.speaker or (speakers[0] if speakers else "ryan")

        status, headers, body = request_binary(
            "POST",
            f"{args.base_url}/synthesize/custom-voice",
            payload={
                "text": args.text,
                "speaker": selected_speaker,
                "language": args.language,
                "model_id": args.model_id,
                "format": "wav",
            },
            timeout=240.0,
        )
        assert_wav_response(status, headers, body, endpoint="/synthesize/custom-voice")

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(body)
        print(f"Wrote WAV: {output_path}")
        return 0
    except Exception as exc:
        print(f"custom_voice_smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
