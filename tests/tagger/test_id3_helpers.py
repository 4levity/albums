from mutagen.id3 import ID3
from mutagen.id3._frames import TALB, TDRL, TPOS, TRCK, UFID
from mutagen.id3._specs import Encoding

from albums.tagger import BasicField
from albums.tagger.id3_helpers import format_numbered_value, get_text, id3_legacy_fields, must_get_text, parse_numbered_value, set_numbered_frame


class TestParseNumberedValue:
    def test_none(self):
        assert parse_numbered_value(None) == (None, None)

    def test_number_only(self):
        assert parse_numbered_value("1") == ("1", None)

    def test_number_and_total(self):
        assert parse_numbered_value("1/3") == ("1", "3")

    def test_empty_parts_are_unset(self):
        assert parse_numbered_value("/3") == (None, "3")
        assert parse_numbered_value("1/") == ("1", None)


class TestFormatNumberedValue:
    def test_none(self):
        assert format_numbered_value(None, None) is None

    def test_number_only(self):
        assert format_numbered_value("1", None) == "1"

    def test_total_only(self):
        assert format_numbered_value(None, "3") == "/3"

    def test_number_and_total(self):
        assert format_numbered_value("1", "3") == "1/3"


class TestSetNumberedFrame:
    def test_adds_frame(self):
        id3 = ID3()
        set_numbered_frame(id3, "1/3", "TRCK", TRCK)
        assert id3["TRCK"].text == ["1/3"]

    def test_updates_frame(self):
        id3 = ID3()
        id3.add(TRCK(encoding=Encoding.UTF8, text=["1/3"]))
        set_numbered_frame(id3, "2/3", "TRCK", TRCK)
        assert id3["TRCK"].text == ["2/3"]

    def test_noop_when_value_unchanged(self):
        id3 = ID3()
        id3.add(TPOS(encoding=Encoding.UTF8, text=["1/2"]))
        set_numbered_frame(id3, "1/2", "TPOS", TPOS)
        assert id3["TPOS"].text == ["1/2"]

    def test_removes_frame(self):
        id3 = ID3()
        id3.add(TPOS(encoding=Encoding.UTF8, text=["1/2"]))
        set_numbered_frame(id3, None, "TPOS", TPOS)
        assert "TPOS" not in id3


class TestId3LegacyFields:
    def test_none_frames(self):
        assert id3_legacy_fields(None) == ()

    def test_no_legacy_frames(self):
        assert id3_legacy_fields(ID3()) == ()

    def test_legacy_frame(self):
        id3 = ID3()
        id3.add(TDRL(encoding=Encoding.UTF8, text=["2019"]))
        assert id3_legacy_fields(id3) == (("TDRL", BasicField.DATE),)


class TestGetText:
    def test_none_id3(self):
        assert get_text(None, "TALB") is None

    def test_missing_frame(self):
        assert get_text(ID3(), "TALB") is None

    def test_present_frame(self):
        id3 = ID3()
        id3.add(TALB(encoding=Encoding.UTF8, text=["baz"]))
        assert get_text(id3, "TALB") == ["baz"]


class TestMustGetText:
    def test_text_frame(self):
        id3 = ID3()
        id3.add(TALB(encoding=Encoding.UTF8, text=["baz"]))
        assert must_get_text(id3, "TALB") == ["baz"]

    def test_non_text_frame_fallback(self):
        # frames without a text list fall back to a single shortened string representation
        id3 = ID3()
        id3.add(UFID(owner="http://musicbrainz.org", data=b"1234"))
        assert len(must_get_text(id3, "UFID:http://musicbrainz.org")) == 1
