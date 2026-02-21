from albums.app import Context
from albums.checks.path.check_cover_filename import CheckCoverFilename
from albums.types import Album, Track


class TestCheckTrackFilename:
    def test_track_filename_ok(self):
        tracks = [
            Track("1 foo.flac", {"tracknumber": ["1"], "title": ["foo"]}),
            Track("2 bar.flac", {"tracknumber": ["2"], "title": ["bar"]}),
        ]
        assert not CheckCoverFilename(Context()).check(Album("", tracks))

    def test_track_filename_disc_ok(self):
        tracks = [
            Track("2-01 foo.flac", {"discnumber": ["2"], "tracknumber": ["01"], "title": ["foo"]}),
            Track("2-02 bar.flac", {"discnumber": ["2"], "tracknumber": ["02"], "title": ["bar"]}),
        ]
        assert not CheckCoverFilename(Context()).check(Album("", tracks))

    def test_track_filename_albumartist_ok(self):
        tracks = [
            Track("1 baz - foo.flac", {"tracknumber": ["1"], "title": ["foo"], "artist": ["baz"], "albumartist": ["Various Artists"]}),
            Track("2 mob - bar.flac", {"tracknumber": ["2"], "title": ["bar"], "artist": ["mob"], "albumartist": ["Various Artists"]}),
        ]
        assert not CheckCoverFilename(Context()).check(Album("", tracks))
