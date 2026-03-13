import os

from albums.app import Context
from albums.checks.path.check_duplicate_pathname import CheckDuplicatePathname
from albums.picture.info import PictureInfo
from albums.types import Album, PictureFile, Track


class TestCheckDuplicatePathname:
    def test_pathname_ok(self):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="normal.1.flac"), Track(filename="normal.2.flac")],
            picture_files=[
                PictureFile(filename="normal.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),
                PictureFile(filename="normal.png", picture_info=PictureInfo("image/png", 1, 1, 1, 1, b"")),
            ],
        )
        assert not CheckDuplicatePathname(Context()).check(album)

    def test_pathname_duplicate_picture_file(self):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="normal.1.flac"), Track(filename="normal.2.flac")],
            picture_files=[
                PictureFile(filename="FileName.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),
                PictureFile(filename="Filename.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),
            ],
        )
        result = CheckDuplicatePathname(Context()).check(album)
        assert result is not None
        assert "2 files are variations of filename.jpg" in result.message

    def test_pathname_duplicate_track_file(self):
        album = Album(
            path="Foo" + os.sep,
            tracks=[Track(filename="track.flac"), Track(filename="Track.flac")],
            picture_files=[
                PictureFile(filename="normal.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),
                PictureFile(filename="normal.png", picture_info=PictureInfo("image/png", 1, 1, 1, 1, b"")),
            ],
        )
        result = CheckDuplicatePathname(Context()).check(album)
        assert result is not None
        assert "2 files are variations of track.flac" in result.message
