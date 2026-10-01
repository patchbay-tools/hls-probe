import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hls_probe  # noqa: E402

MASTER = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,CODECS="avc1.4d401e,mp4a.40.2"
360p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2800000,RESOLUTION=1280x720,CODECS="avc1.4d401f,mp4a.40.2"
720p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
https://cdn.example.net/live/1080p/index.m3u8
"""

MEDIA = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:1041
#EXTINF:6.000,
seg1041.ts
#EXTINF:6.006,
seg1042.ts
#EXTINF:5.972,
seg1043.ts
"""


class ParseTests(unittest.TestCase):
    base = "https://origin.example.net/live/master.m3u8"

    def test_attributes_with_quoted_commas(self):
        attrs = hls_probe.parse_attributes('BANDWIDTH=1,CODECS="a,b",X=y')
        self.assertEqual(attrs, {"BANDWIDTH": "1", "CODECS": "a,b", "X": "y"})

    def test_master_variants(self):
        self.assertTrue(hls_probe.is_master(MASTER))
        variants = hls_probe.parse_master(MASTER, self.base)
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].uri,
                         "https://origin.example.net/live/360p/index.m3u8")
        self.assertEqual(variants[2].uri,
                         "https://cdn.example.net/live/1080p/index.m3u8")

    def test_pick_variant(self):
        variants = hls_probe.parse_master(MASTER, self.base)
        self.assertEqual(hls_probe.pick_variant(variants, "lowest").bandwidth, 800000)
        self.assertEqual(hls_probe.pick_variant(variants, "middle").bandwidth, 2800000)
        self.assertEqual(hls_probe.pick_variant(variants, "highest").bandwidth, 5000000)

    def test_media_playlist(self):
        self.assertFalse(hls_probe.is_master(MEDIA))
        pl = hls_probe.parse_media(MEDIA, self.base)
        self.assertEqual(pl.target_duration, 6)
        self.assertEqual(pl.media_sequence, 1041)
        self.assertFalse(pl.endlist)
        self.assertEqual([s.duration for s in pl.segments], [6.0, 6.006, 5.972])
        self.assertTrue(pl.segments[-1].uri.endswith("/live/seg1043.ts"))

    def test_exceeds_target_rounds_duration(self):
        self.assertFalse(hls_probe.exceeds_target(6.006, 6))
        self.assertFalse(hls_probe.exceeds_target(6.4, 6))
        self.assertTrue(hls_probe.exceeds_target(6.5, 6))
        self.assertFalse(hls_probe.exceeds_target(9.0, 0))


if __name__ == "__main__":
    unittest.main()
