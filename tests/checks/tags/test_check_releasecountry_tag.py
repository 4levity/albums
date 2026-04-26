from albums.app import Context
from albums.checks.tags.check_releasecountry_tag import CheckReleaseCountryTag
from albums.types import Album, BasicTag, Track


class TestCheckReleaseCountryTag:
    def test_releasecountry_ok(self):
        tracks = [Track(filename="1.flac", tag={BasicTag.RELEASECOUNTRY: "US"}), Track(filename="2.flac", tag={BasicTag.RELEASECOUNTRY: "US"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseCountryTag(Context()).check(album)
        assert result is None

    def test_releasecountry_ok_none(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseCountryTag(Context()).check(album)
        assert result is None

    def test_releasecountry_ok_inconsistent(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac", tag={BasicTag.RELEASECOUNTRY: "US"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseCountryTag(Context()).check(album)
        assert result is not None
        assert "releasecountry policy=CONSISTENT but it is on some tracks and not others" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["US", ">> Remove tag releasecountry"]
        assert result.fixer.option_automatic_index == 0

    def test_releasecountry_ok_inconsistent_mixed(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.mp3", tag={BasicTag.RELEASECOUNTRY: "US"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseCountryTag(Context()).check(album)
        assert result is not None
        assert "releasecountry policy=NEVER but it appears on tracks" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove tag releasecountry"]
        assert result.fixer.option_automatic_index == 0
