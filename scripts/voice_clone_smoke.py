from __future__ import annotations

import argparse
import base64
from pathlib import Path
import sys

from smoke_common import assert_wav_response, ensure_healthy, load_mode_and_wait, request_binary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run API e2e smoke test for voice clone synthesis.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="TalkToMePy service base URL.")
    parser.add_argument("--model-id", default="Qwen/Qwen3-TTS-12Hz-1.7B-Base", help="Voice clone model id.")
    parser.add_argument("--text", default="Hello from voice clone smoke test.", help="Text to synthesize.")
    parser.add_argument("--language", default="English", help="Language to synthesize.")
    parser.add_argument("--output", default="outputs/voice_clone_smoke.wav", help="Output WAV file path.")
    parser.add_argument(
        "--validate-data-url",
        action="store_true",
        help="Also validate data URL base64 input variant for reference audio.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        ensure_healthy(args.base_url)

        # Build reference audio from voice-design synthesis output.
        status, headers, ref_wav = request_binary(
            "POST",
            f"{args.base_url}/synthesize/voice-design",
            payload={
                "text": "Reference audio for clone smoke test.",
                "instruct": "Warm and clear narrator voice.",
                "language": args.language,
                "format": "wav",
            },
            timeout=240.0,
        )
        assert_wav_response(status, headers, ref_wav, endpoint="/synthesize/voice-design")
        ref_b64 = base64.b64encode(ref_wav).decode("ascii")

        load_mode_and_wait(args.base_url, mode="voice_clone")

        status, headers, body = request_binary(
            "POST",
            f"{args.base_url}/synthesize/voice-clone",
            payload={
                "text": args.text,
                "reference_audio_b64": ref_b64,
                "language": args.language,
                "model_id": args.model_id,
                "format": "wav",
            },
            timeout=240.0,
        )
        assert_wav_response(status, headers, body, endpoint="/synthesize/voice-clone")

        if args.validate_data_url:
            status, headers, body_data_url = request_binary(
                "POST",
                f"{args.base_url}/synthesize/voice-clone",
                payload={
                    "text": args.text,
                    "reference_audio_b64": f"data:audio/wav;base64,{ref_b64}",
                    "language": args.language,
                    "model_id": args.model_id,
                    "format": "wav",
                },
                timeout=240.0,
            )
            assert_wav_response(status, headers, body_data_url, endpoint="/synthesize/voice-clone[data-url]")

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(body)
        print(f"Wrote WAV: {output_path}")
        return 0
    except Exception as exc:
        print(f"voice_clone_smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
