#!/usr/bin/env python3
"""Probe an HLS playlist and report segment latency.

Fetches a master or media playlist, picks a variant, then times the last
few segments: time to first byte, total fetch time and throughput, and
compares each segment's duration against the playlist's target duration.
"""

import argparse
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urljoin

USER_AGENT = "hls-probe/0.3"


@dataclass
class Variant:
    uri: str
    bandwidth: int = 0
    resolution: str = ""


@dataclass
class Segment:
    uri: str
    duration: float


@dataclass
class MediaPlaylist:
    target_duration: float = 0.0
    media_sequence: int = 0
    endlist: bool = False
    segments: list = field(default_factory=list)


def parse_attributes(text):
    """Parse an EXT-X attribute list, honouring quoted values."""
    attrs = {}
    key, value, quoted, in_value = "", "", False, False
    for ch in text + ",":
        if in_value:
            if ch == '"':
                quoted = not quoted
            elif ch == "," and not quoted:
                attrs[key.strip()] = value.strip('"')
                key, value, in_value = "", "", False
            else:
                value += ch
        elif ch == "=":
            in_value = True
        else:
            key += ch
    return attrs


def is_master(text):
    return "#EXT-X-STREAM-INF" in text


def parse_master(text, base_url):
    variants = []
    pending = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXT-X-STREAM-INF:"):
            pending = parse_attributes(line.split(":", 1)[1])
        elif line and not line.startswith("#") and pending is not None:
            variants.append(Variant(
                uri=urljoin(base_url, line),
                bandwidth=int(pending.get("BANDWIDTH", 0)),
                resolution=pending.get("RESOLUTION", ""),
            ))
            pending = None
    return variants


def parse_media(text, base_url):
    playlist = MediaPlaylist()
    duration = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXT-X-TARGETDURATION:"):
            playlist.target_duration = float(line.split(":", 1)[1])
        elif line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            playlist.media_sequence = int(line.split(":", 1)[1])
        elif line.startswith("#EXT-X-ENDLIST"):
            playlist.endlist = True
        elif line.startswith("#EXTINF:"):
            duration = float(line.split(":", 1)[1].split(",", 1)[0])
        elif line and not line.startswith("#") and duration is not None:
            playlist.segments.append(Segment(urljoin(base_url, line), duration))
            duration = None
    return playlist


def pick_variant(variants, mode):
    ordered = sorted(variants, key=lambda v: v.bandwidth)
    if mode == "lowest":
        return ordered[0]
    if mode == "highest":
        return ordered[-1]
    return ordered[len(ordered) // 2]


def fetch(url, timeout):
    """Return (body, ttfb seconds, total seconds)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        first = resp.read(1)
        ttfb = time.monotonic() - start
        body = first + resp.read()
    return body, ttfb, time.monotonic() - start


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url", help="master or media playlist URL")
    ap.add_argument("-n", "--segments", type=int, default=3,
                    help="how many of the newest segments to fetch (default 3)")
    ap.add_argument("--variant", choices=("lowest", "middle", "highest"),
                    default="highest")
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args(argv)

    body, ttfb, total = fetch(args.url, args.timeout)
    text = body.decode("utf-8", "replace")
    url = args.url
    print(f"playlist  {url}  ttfb={ttfb * 1000:.0f}ms total={total * 1000:.0f}ms")

    if is_master(text):
        variants = parse_master(text, url)
        if not variants:
            print("master playlist has no variants", file=sys.stderr)
            return 2
        chosen = pick_variant(variants, args.variant)
        print(f"variant   {chosen.bandwidth} bps {chosen.resolution or '-'}")
        url = chosen.uri
        text = fetch(url, args.timeout)[0].decode("utf-8", "replace")

    playlist = parse_media(text, url)
    if not playlist.segments:
        print("media playlist has no segments", file=sys.stderr)
        return 2

    late = 0
    for seg in playlist.segments[-args.segments:]:
        data, seg_ttfb, seg_total = fetch(seg.uri, args.timeout)
        mbps = len(data) * 8 / seg_total / 1e6 if seg_total else 0.0
        over = seg.duration > playlist.target_duration > 0
        slow = seg_total > seg.duration
        late += slow
        flags = " ".join(f for f, on in (("OVER-TARGET", over), ("SLOW", slow)) if on)
        print(f"segment   {seg.duration:5.2f}s/{playlist.target_duration:g}s "
              f"ttfb={seg_ttfb * 1000:4.0f}ms total={seg_total * 1000:5.0f}ms "
              f"{mbps:6.2f} Mbit/s {flags}")

    return 1 if late else 0


if __name__ == "__main__":
    sys.exit(main())
