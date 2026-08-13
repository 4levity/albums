from albums.app import Context
from albums.checks.fields.check_releasetype import CheckReleaseTypeField
from albums.entities import Album, Track
from albums.tagger import BasicField


class TestCheckReleaseTypeField:
    def test_releasetype_ok(self):
        tracks = [Track(filename="1.flac", tag={BasicField.RELEASETYPE: "Album"}), Track(filename="2.flac", tag={BasicField.RELEASETYPE: "Album"})]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseTypeField(Context()).check(album)
        assert result is None

    def test_releasetype_ok_none(self):
        tracks = [Track(filename="1.flac"), Track(filename="2.flac")]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseTypeField(Context()).check(album)
        assert result is None

    def test_releasetype_ok_multi(self):
        tracks = [
            Track(filename="1.flac", tag={BasicField.RELEASETYPE: ["Live", "Album"]}),
            Track(filename="2.flac", tag={BasicField.RELEASETYPE: ["Live", "Album"]}),
        ]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseTypeField(Context()).check(album)
        assert result is None

    def test_releasetype_conflict_multi(self):
        tracks = [
            Track(filename="1.flac", tag={BasicField.RELEASETYPE: ["Live", "Album"]}),
            Track(filename="2.flac", tag={BasicField.RELEASETYPE: ["Live"]}),
        ]
        album = Album(path="foo", tracks=tracks)
        result = CheckReleaseTypeField(Context()).check(album)
        assert result is not None
        assert result.message == "multiple values for releasetype: ('Live', 'Album'), ('Live',)"
        assert result.fixer is not None
        assert result.fixer.options == ["Live", "Live, Album", ">> Remove releasetype from all tracks"]
        assert result.fixer.option_automatic_index is None
