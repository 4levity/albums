import os
from pathlib import Path
from typing import Sequence
from unittest.mock import call

from rich_pixels import Pixels
from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.picture.check_cover_unique import CheckCoverUnique
from albums.database import connection
from albums.database.models import AlbumEntity
from albums.database.operations import album_to_album
from albums.library import scanner
from albums.picture.info import PictureInfo
from albums.tagger.types import Picture, PictureType, StreamInfo
from albums.types import Album, PictureFile, Track

from ...fixtures.create_library import create_library


class TestCheckCoverUnique:
    def test_cover_ok(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [
                        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, ""),
                        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, ""),
                    ],
                ),
                Track(
                    "2.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [
                        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, ""),
                        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, ""),
                    ],
                ),
            ],
        )
        assert not CheckCoverUnique(Context()).check(album)

    def test_cover_multiple_unique(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, "")],
                ),
                Track(
                    "2.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 500, 500, 24, 1, b""), PictureType.COVER_FRONT, "")],
                ),
            ],
        )
        result = CheckCoverUnique(Context()).check(album)
        assert result is not None
        assert result.message == "all tracks have cover pictures, but not all cover pictures are the same"
        assert result.fixer
        assert result.fixer.options == []

    def test_has_unmarked_cover_source_file(self, mocker):
        picture_files = [PictureFile("cover.png", PictureInfo("image/png", 1000, 1000, 24, 10000, b""), 0, False)]
        album = Album(
            "foo" + os.sep,
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, "")],
                )
            ],
            [],
            [],
            picture_files,
        )
        ctx = Context()
        ctx.config.library = create_library("front_cover", [album])
        # actually scan and load the album so picture hashes will be correct
        ctx.db = connection.open(connection.MEMORY)
        try:
            scanner.scan(ctx)
            with Session(ctx.db) as session:
                album = album_to_album(session.execute(select(AlbumEntity)).tuples().one()[0], True)
        finally:
            ctx.db.dispose()

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

        update_picture_files_mock = mocker.patch("albums.checks.picture.check_cover_unique.update_picture_files")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert update_picture_files_mock.call_count == 1
        assert update_picture_files_mock.call_args.args[1] == album.album_id
        picture_files: Sequence[PictureFile] = update_picture_files_mock.call_args.args[2]
        cover = next(file for file in picture_files if file.filename == "cover.png")
        assert cover.cover_source

    def test_multiple_cover_image_files_no_embedded(self, mocker):
        picture_files = [
            PictureFile("cover_big.png", PictureInfo("image/png", 1000, 1000, 24, 10000, b"1111"), 0, False),
            PictureFile("cover_small.png", PictureInfo("image/png", 1000, 1000, 24, 1000, b"2222"), 0, False),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"))], [], [], picture_files, 999)
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

        update_picture_files_mock = mocker.patch("albums.checks.picture.check_cover_unique.update_picture_files")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert update_picture_files_mock.call_count == 1
        assert update_picture_files_mock.call_args.args[1] == 999
        picture_files: Sequence[PictureFile] = update_picture_files_mock.call_args.args[2]
        cover = next(file for file in picture_files if file.filename == "cover_big.png")
        assert cover.cover_source

    def test_multiple_cover_image_files_with_cover_source(self, mocker):
        picture_files = [
            PictureFile("cover_big.png", PictureInfo("image/png", 1000, 1000, 24, 10000, b"1111"), 0, True),
            PictureFile("cover_small.png", PictureInfo("image/png", 1000, 1000, 24, 1000, b"2222"), 0, False),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"))], [], [], picture_files, 999)
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
