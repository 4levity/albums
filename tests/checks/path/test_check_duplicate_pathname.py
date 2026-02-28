import os

from albums.app import Context
from albums.checks.path.check_duplicate_pathname import CheckDuplicatePathname
from albums.picture.info import PictureInfo
from albums.tagger.types import Picture, PictureType
from albums.types import Album, PictureFile, Track


class TestCheckDuplicatePathname:
    def test_pathname_ok(self):
        album = Album(
            "Foo" + os.sep,
            [Track("normal.1.flac"), Track("normal.2.flac")],
            [],
            [],
            {
                "normal.jpg": PictureFile(Picture(PictureInfo("image/jpeg", 1, 1, 1, 1, b""), PictureType.COVER_FRONT, "", ()), 0, False),
                "normal.png": PictureFile(Picture(PictureInfo("image/png", 1, 1, 1, 1, b""), PictureType.COVER_FRONT, "", ()), 0, False),
            },
        )
        assert not CheckDuplicatePathname(Context()).check(album)

    def test_pathname_duplicate_picture_file(self):
        album = Album(
            "Foo" + os.sep,
            [Track("normal.1.flac"), Track("normal.2.flac")],
            [],
            [],
            {
                "FileName.jpg": PictureFile(Picture(PictureInfo("image/jpeg", 1, 1, 1, 1, b""), PictureType.COVER_FRONT, "", ()), 0, False),
                "Filename.jpg": PictureFile(Picture(PictureInfo("image/jpeg", 1, 1, 1, 1, b""), PictureType.COVER_FRONT, "", ()), 0, False),
            },
        )
        result = CheckDuplicatePathname(Context()).check(album)
        assert result is not None
        assert "2 files are variations of filename.jpg" in result.message

    def test_pathname_duplicate_track_file(self):
        album = Album(
            "Foo" + os.sep,
            [Track("track.flac"), Track("Track.flac")],
            [],
            [],
            {
                "normal.jpg": PictureFile(Picture(PictureInfo("image/jpeg", 1, 1, 1, 1, b""), PictureType.COVER_FRONT, "", ()), 0, False),
                "normal.png": PictureFile(Picture(PictureInfo("image/png", 1, 1, 1, 1, b""), PictureType.COVER_FRONT, "", ()), 0, False),
            },
        )
        result = CheckDuplicatePathname(Context()).check(album)
        assert result is not None
        assert "2 files are variations of track.flac" in result.message
