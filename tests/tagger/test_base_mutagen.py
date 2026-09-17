from albums.tagger.base_mutagen import _find_codec, _get_stream_info
from albums.tagger.types import StreamInfo


class TestGetStreamInfo:
    def test_missing_attributes_default_to_zero(self, caplog):
        caplog.set_level("WARNING")

        class BareInfo:
            pass

        assert _get_stream_info("file", BareInfo(), "codec") == StreamInfo(0.0, 0, 0, "codec", 0, 0)
        assert len([record for record in caplog.records if "couldn't determine" in record.message]) == 4

    def test_present_attributes_are_converted(self):
        class Info:
            length = 1.5
            bitrate = 192_000
            channels = 2
            sample_rate = 44_100
            bits_per_sample = 16

        assert _get_stream_info("file", Info(), "codec") == StreamInfo(1.5, 192_000, 2, "codec", 44_100, 16)


class TestFindCodec:
    def test_codec_name(self):
        class Info:
            codec_name = "FLAC"

        assert _find_codec(Info()) == "FLAC"

    def test_codec(self):
        class Info:
            codec = "MPEG Layer 3"

        assert _find_codec(Info()) == "MPEG Layer 3"

    def test_pprint_first_item(self):
        class Info:
            def pprint(self):
                return "MP3, 128 kbps, stereo"

        assert _find_codec(Info()) == "MP3"

    def test_unrecognized(self):
        class Info:
            pass

        assert _find_codec(Info()) is None
