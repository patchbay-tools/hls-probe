# hls-probe

Probe an HLS playlist and report segment latency.

Given a master or media playlist URL, `hls-probe` picks a variant, fetches the
newest few segments and prints, per segment:

- time to first byte and total fetch time
- throughput in Mbit/s
- the segment's `#EXTINF` duration against `#EXT-X-TARGETDURATION`

A segment that takes longer to download than it takes to play is flagged
`SLOW`; one longer than the target duration is flagged `OVER-TARGET`.

No dependencies beyond Python 3.8+.

## Usage

```
./hls_probe.py https://example.net/live/master.m3u8
./hls_probe.py -n 5 --variant lowest https://example.net/live/master.m3u8
```

```
playlist  https://example.net/live/master.m3u8  ttfb=42ms total=43ms
variant   5000000 bps 1920x1080
segment    6.00s/6s ttfb=  61ms total=  412ms  59.21 Mbit/s
segment    6.01s/6s ttfb=  58ms total=  398ms  61.02 Mbit/s
segment    5.97s/6s ttfb=  66ms total=  440ms  55.37 Mbit/s
```

Exit status is 0 when every segment downloaded faster than real time, 1 when
any was slow, 2 when the playlist could not be used. That makes it usable
from cron or a monitoring check.

## Tests

```
python3 -m unittest discover tests
```
