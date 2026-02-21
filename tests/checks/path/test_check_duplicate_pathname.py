import os

from albums.app import Context
from albums.checks.path.check_duplicate_pathname import CheckDuplicatePathname
from albums.types import Album, Picture, PictureType, Track


class TestCheckDuplicatePathname:
    def test_pathname_ok(self):
        album = Album(
            "Foo" + os.sep,
            [Track("normal.1.flac"), Track("normal.2.flac")],
            [],
            [],
            {
                "normal.jpg": Picture(PictureType.OTHER, "image/jpeg", 1, 1, 1, b""),
                "normal.png": Picture(PictureType.OTHER, "image/jpeg", 1, 1, 1, b""),
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
                "FileName.jpg": Picture(PictureType.OTHER, "image/jpeg", 1, 1, 1, b""),
                "Filename.jpg": Picture(PictureType.OTHER, "image/jpeg", 1, 1, 1, b""),
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
                "normal.jpg": Picture(PictureType.OTHER, "image/jpeg", 1, 1, 1, b""),
                "normal.png": Picture(PictureType.OTHER, "image/jpeg", 1, 1, 1, b""),
            },
        )
        result = CheckDuplicatePathname(Context()).check(album)
        assert result is not None
        assert "2 files are variations of track.flac" in result.message
