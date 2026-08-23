#!/usr/bin/env python3
"""Convert an SRT caption file into the raw JSON source accepted by the extractor."""
import argparse
import json
import re
from pathlib import Path


TIMING = re.compile(r"(\d\d):(\d\d):(\d\d)[,.](\d\d\d)\s+-->\s+(\d\d):(\d\d):(\d\d)[,.](\d\d\d)")
MARKUP = re.compile(r"<[^>]+>")


def seconds(parts):
    h, m, s, ms = (int(x) for x in parts)
    return h * 3600 + m * 60 + s + ms / 1000


def stamp(value):
    value = int(value)
    return f"{value // 3600:02d}:{value % 3600 // 60:02d}:{value % 60:02d}"


def parse_srt(text):
    blocks = re.split(r"\n\s*\n", text.strip())
    segments = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        match = TIMING.search(lines[timing_index])
        if not match:
            continue
        start, end = seconds(match.groups()[:4]), seconds(match.groups()[4:])
        body = MARKUP.sub("", " ".join(lines[timing_index + 1:]))
        if body:
            segments.append({"start_sec": round(start, 3), "end_sec": round(end, 3), "text": body})
    return segments


def extraction_segments(segments):
    """Drop rolling duplicates produced by YouTube auto-captions.

    The original ``segments`` and ``text`` remain untouched for auditability.
    This view exists solely to give the extractor a readable, non-repeating
    transcript.  A segment is retained only for the words it adds beyond the
    longest suffix/prefix overlap with the preceding retained text.
    """
    result = []
    previous_words = []
    for segment in segments:
        words = segment["text"].split()
        if not words:
            continue
        max_overlap = min(len(previous_words), len(words))
        overlap = 0
        for size in range(max_overlap, 0, -1):
            if previous_words[-size:] == words[:size]:
                overlap = size
                break
        added = words[overlap:]
        if added:
            result.append({**segment, "text": " ".join(added)})
            previous_words.extend(added)
        # Keep a bounded context: caption overlaps are local, and a bound
        # prevents long recordings from becoming needlessly expensive here.
        previous_words = previous_words[-160:]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("srt", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--published-at", required=True)
    parser.add_argument("--external-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    segments = parse_srt(args.srt.read_text(encoding="utf-8"))
    if not segments:
        raise SystemExit("No usable SRT segments")
    text = "\n".join(f"[{stamp(s['start_sec'])}] {s['text']}" for s in segments)
    clean_segments = extraction_segments(segments)
    extraction_text = "\n".join(f"[{stamp(s['start_sec'])}] {s['text']}" for s in clean_segments)
    source = {
        "source_type": "youtube", "source_title": args.title, "source_url": args.url,
        "source_external_id": args.external_id, "published_at": args.published_at,
        "caption_origin": "youtube_auto", "segments": segments, "text": text,
        "extraction_text": extraction_text,
    }
    args.output.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"segments": len(segments), "extraction_segments": len(clean_segments), "first_start": segments[0]["start_sec"], "last_end": segments[-1]["end_sec"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
