from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

import soundfile as sf
import torch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a one-shot Qwen3 VoiceDesign synthesis and write a WAV file."
    )
    parser.add_argument(
        "--model",
        default="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        help="Hugging Face model id or local path.",
    )
    parser.add_argument(
        "--text",
        default="Hello from TalkToMePy. This is a Qwen three voice design smoke test.",
        help="Text to synthesize.",
    )
    parser.add_argument(
        "--instruct",
        default="A warm and calm narrator voice with medium pace and clear pronunciation.",
        help="Natural-language voice design instruction.",
    )
    parser.add_argument(
        "--language",
        default="English",
        help="Language name accepted by the model, for example English.",
    )
    parser.add_argument(
        "--output",
        default="outputs/voice_design_smoke.wav",
        help="Output WAV file path.",
    )
    parser.add_argument(
        "--device-map",
        default="auto",
        help="Value passed to from_pretrained(..., device_map=...).",
    )
    parser.add_argument(
        "--dtype",
        choices=("auto", "float16", "bfloat16", "float32"),
        default="auto",
        help="Optional torch dtype for model loading.",
    )
    return parser.parse_args()


def resolve_dtype(dtype: str):
    if dtype == "float16":
        return torch.float16
    if dtype == "bfloat16":
        return torch.bfloat16
    if dtype == "float32":
        return torch.float32
    return None


def main() -> int:
    args = parse_args()

    if shutil.which("sox") is None:
        print(
            "Missing system dependency: `sox` is not on PATH. "
            "Install it first (for macOS: `brew install sox`).",
            file=sys.stderr,
        )
        return 1

    # Import after checking SoX to keep errors clear for first-time setup.
    from qwen_tts import Qwen3TTSModel

    load_kwargs = {}
    if args.device_map:
        load_kwargs["device_map"] = args.device_map

    dtype = resolve_dtype(args.dtype)
    if dtype is not None:
        load_kwargs["torch_dtype"] = dtype

    print(f"Loading model: {args.model}")
    model = Qwen3TTSModel.from_pretrained(args.model, **load_kwargs)

    print("Generating audio...")
    wavs, sample_rate = model.generate_voice_design(
        text=args.text,
        instruct=args.instruct,
        language=args.language,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, wavs[0], sample_rate)
    print(f"Wrote WAV: {output_path} (sample_rate={sample_rate})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

