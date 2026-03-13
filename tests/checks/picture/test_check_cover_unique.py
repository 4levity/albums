import os
from pathlib import Path
from unittest.mock import call

from rich_pixels import Pixels
from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.picture.check_cover_unique import CheckCoverUnique
from albums.database import connection
from albums.library import scanner
from albums.picture.info import PictureInfo
from albums.tagger.types import PictureType
from albums.types import Album, PictureFile, Track, TrackPicture

from ...fixtures.create_library import create_library


class TestCheckCoverUnique:
    def test_cover_ok(self):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                    ],
                ),
                Track(
                    filename="2.flac",
                    pictures=[
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
                        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK),
                    ],
                ),
            ],
        )
        assert not CheckCoverUnique(Context()).check(album)

    def test_cover_multiple_unique(self):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT)],
                ),
                Track(
                    filename="2.flac",
                    pictures=[TrackPicture(picture_info=PictureInfo("image/png", 500, 500, 24, 1, b""), picture_type=PictureType.COVER_FRONT)],
                ),
            ],
        )
        result = CheckCoverUnique(Context()).check(album)
        assert result is not None
        assert result.message == "all tracks have cover pictures, but not all cover pictures are the same"
        assert result.fixer
        assert result.fixer.options == []

    def test_has_unmarked_cover_source_file(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT)],
                )
            ],
            picture_files=[PictureFile(filename="cover.png", picture_info=PictureInfo("image/png", 1000, 1000, 24, 10000, b""))],
        )
        ctx = Context()
        ctx.config.library = create_library("front_cover", [album])
        ctx.db = connection.open(connection.MEMORY)
        try:
            with Session(ctx.db) as session:
                scanner.scan(ctx, session)
                (album,) = session.execute(select(Album)).tuples().one()
                result = CheckCoverUnique(ctx).check(album)
                assert result is not None
                assert (
                    result.message
                    == "multiple cover art images: designate a high-resolution image file as cover art source or delete image files (keep embedded images)"
                )
                assert result.fixer
                assert result.fixer.options == [">> Mark as front cover source: cover.png", ">> Delete all cover image files: cover.png"]
                assert result.fixer.option_automatic_index == 0
                table = result.fixer.get_table()
                assert table
                (headers, rows) = table
                assert len(headers) == 2
                assert len(rows) == 2
                assert len(rows[0]) == 2
                assert isinstance(rows[0][0], Pixels)
                assert isinstance(rows[0][1], Pixels)
                assert "1000 x 1000" in str(rows[1][0])
                assert "400 x 400" in str(rows[1][1])

                fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

                assert fix_result
                assert album.picture_files[0].cover_source

        finally:
            ctx.db.dispose()

    def test_multiple_cover_image_files_no_embedded(self, mocker):
        album = Album(
            path="",
            tracks=[Track(filename="1.flac")],
            picture_files=[
                PictureFile(filename="cover_big.png", picture_info=PictureInfo("image/png", 1000, 1000, 24, 10000, b"1111")),
                PictureFile(filename="cover_small.png", picture_info=PictureInfo("image/png", 1000, 1000, 24, 1000, b"2222")),
            ],
        )
        ctx = Context()
        ctx.db = True
        result = CheckCoverUnique(ctx).check(album)
        assert result is not None
        assert (
            result.message
            == "multiple cover art images: designate a high-resolution image file as cover art source (tracks do not have embedded images)"
        )
        assert result.fixer
        assert result.fixer.options == [">> Mark as front cover source: cover_big.png", ">> Mark as front cover source: cover_small.png"]
        assert result.fixer.option_automatic_index == 0

        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert fix_result
        cover = next(file for file in album.picture_files if file.filename == "cover_big.png")
        assert cover.filename == "cover_big.png"
        assert cover.cover_source

    def test_multiple_cover_image_files_with_cover_source(self, mocker):
        album = Album(
            path="",
            tracks=[Track(filename="1.flac")],
            picture_files=[
                PictureFile(filename="cover_big.png", picture_info=PictureInfo("image/png", 1000, 1000, 24, 10000, b"1111"), cover_source=True),
                PictureFile(filename="cover_small.png", picture_info=PictureInfo("image/png", 1000, 1000, 24, 1000, b"2222"), cover_source=False),
            ],
        )
        ctx = Context()
        ctx.db = True
        result = CheckCoverUnique(ctx).check(album)
        assert result is not None
        assert result.message == "multiple front cover image files, and one of them is marked cover source (delete others)"
        assert result.fixer
        assert result.fixer.options == ['>> Keep cover source image "cover_big.png" and delete other cover files: cover_small.png']
        assert result.fixer.option_automatic_index == 0

        mock_unlink = mocker.patch("albums.checks.helpers.unlink")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_unlink.call_args_list == [call(Path(album.path) / "cover_small.png")]
