#!/usr/bin/env python3
"""Run a Experts Said extraction prompt via OpenClaw and save the raw response."""
import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--transcript", type=Path, help="reuse the final assistant JSON stored by an OpenClaw session")
    parser.add_argument("--source", type=Path, help="raw source JSON; restores source text and quote-verification view")
    args = parser.parse_args()
    if args.transcript:
        response = ""
        for line in args.transcript.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            message = entry.get("message", {})
            if message.get("role") == "assistant":
                blocks = message.get("content", [])
                response = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        if not response:
            raise SystemExit("No assistant response found in transcript")
    else:
        prompt = args.prompt.read_text(encoding="utf-8")
    # `infer model run --prompt` puts the complete source into argv and exceeds
    # the OS argument-size limit for long transcripts. The gateway agent accepts
    # a prompt file, preserving the same model choice without truncation.
        model_id = {"GLM": "zai/glm-5.2", "Terra": "openai/gpt-5.6-terra"}[args.model]
        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--model", model_id,
             "--message-file", str(args.prompt), "--timeout", str(args.timeout)],
            check=True, text=True, capture_output=True, timeout=args.timeout,
        )
        response = result.stdout.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    # The CLI may prefix the assistant message with a transport status line.
    first, last = response.find("{"), response.rfind("}")
    if first >= 0 and last > first:
        response = response[first:last + 1]
    doc = json.loads(response)
    if args.source:
        source = json.loads(args.source.read_text(encoding="utf-8"))
        # Models occasionally omit the required full text to save tokens. The
        # durable source artifact is authoritative, so restore it rather than
        # accepting an empty or altered model copy. Quotes are checked against
        # a whitespace-only rendering of the deduplicated segments: timestamps
        # are metadata, not spoken words.
        doc["text"] = source["text"]
        extraction = source.get("extraction_text", source["text"])
        doc["quote_verification_text"] = " ".join(
            line.split("] ", 1)[-1] for line in extraction.splitlines()
        )
    response = json.dumps(doc, ensure_ascii=False)
    args.output.write_text(response + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({len(response)} chars)")


if __name__ == "__main__":
    main()
