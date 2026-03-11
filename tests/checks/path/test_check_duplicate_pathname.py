import os

from albums.app import Context
from albums.checks.path.check_duplicate_pathname import CheckDuplicatePathname
from albums.database.models import AlbumEntity, PictureFileEntity, TrackEntity
from albums.picture.info import PictureInfo


class TestCheckDuplicatePathname:
    def test_pathname_ok(self):
        album = AlbumEntity(
            path="Foo" + os.sep,
            tracks=[TrackEntity(filename="normal.1.flac"), TrackEntity(filename="normal.2.flac")],
            picture_files=[
                PictureFileEntity(filename="normal.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),
                PictureFileEntity(filename="normal.png", picture_info=PictureInfo("image/png", 1, 1, 1, 1, b"")),
            ],
        )
        assert not CheckDuplicatePathname(Context()).check(album)

    def test_pathname_duplicate_picture_file(self):
        album = AlbumEntity(
            path="Foo" + os.sep,
            tracks=[TrackEntity(filename="normal.1.flac"), TrackEntity(filename="normal.2.flac")],
            picture_files=[
                PictureFileEntity(filename="FileName.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),
                PictureFileEntity(filename="Filename.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),
            ],
        )
        result = CheckDuplicatePathname(Context()).check(album)
        assert result is not None
        assert "2 files are variations of filename.jpg" in result.message

    def test_pathname_duplicate_track_file(self):
        album = AlbumEntity(
            path="Foo" + os.sep,
            tracks=[TrackEntity(filename="track.flac"), TrackEntity(filename="Track.flac")],
            picture_files=[
                PictureFileEntity(filename="normal.jpg", picture_info=PictureInfo("image/jpeg", 1, 1, 1, 1, b"")),
                PictureFileEntity(filename="normal.png", picture_info=PictureInfo("image/png", 1, 1, 1, 1, b"")),
            ],
        )
        result = CheckDuplicatePathname(Context()).check(album)
        assert result is not None
        assert "2 files are variations of track.flac" in result.message
