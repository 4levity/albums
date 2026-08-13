from albums.app import Context
from albums.checks.fields.check_releasecountry import CheckReleaseCountryField
from albums.entities import Album, Track
from albums.tagger import BasicField


class TestCheckReleaseCountryField:
    def test_releasecountry_ok(self):
        tracks = [Track(filename="1.flac", tag={BasicField.RELEASECOUNTRY: "US"}), Track(filename="2.flac", tag={BasicField.RELEASECOUNTRY: "US"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseCountryField(Context()).check(album)
        assert result is None

    def test_releasecountry_ok_none(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseCountryField(Context()).check(album)
        assert result is None

    def test_releasecountry_ok_inconsistent(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac", tag={BasicField.RELEASECOUNTRY: "US"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseCountryField(Context()).check(album)
        assert result is not None
        assert "releasecountry policy=CONSISTENT but it is on some tracks and not others" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["US", ">> Remove field releasecountry"]
        assert result.fixer.option_automatic_index == 0

    def test_releasecountry_ok_inconsistent_mixed(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.mp3", tag={BasicField.RELEASECOUNTRY: "US"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseCountryField(Context()).check(album)
        assert result is not None
        assert "releasecountry policy=NEVER but it appears on tracks" in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Remove field releasecountry"]
        assert result.fixer.option_automatic_index == 0
