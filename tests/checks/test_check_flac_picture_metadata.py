import contextlib

from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture

from albums.app import Context
from albums.checks.check_flac_picture_metadata import CheckFlacPictureMetadata
from albums.database import connection, selector
from albums.library.scanner import scan
from albums.types import Album, Picture, PictureType, Stream, Track

from ..fixtures.create_library import create_library
from ..fixtures.empty_files import IMAGE_PNG_400X400


class TestCheckFlacPictureMetadata:
    def test_album_art_metadata_mismatch(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", {"format": "image/jpeg"})],
                )
            ],
        )
        result = CheckFlacPictureMetadata(Context()).check(album)
        assert result is not None
        assert result.message == "embedded image metadata mismatch on 1 tracks, example image/png 400x400 but container says image/jpeg 400x400"
        assert result.fixer

    def test_album_art_metadata_mismatch_fix(self):
        album = Album("foo", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))])
        ctx = Context()
        ctx.library_root = create_library("flac_picture_metadata", [album])
        file = ctx.library_root / album.path / album.tracks[0].filename
        flac = FLAC(file)
        pic = FlacPicture()
        pic.data = IMAGE_PNG_400X400
        pic.type = PictureType.COVER_FRONT
        pic.mime = "image/jpeg"
        pic.width = 399
        pic.height = 399
        pic.depth = 1
        flac.add_picture(pic)
        flac.save()

        with contextlib.closing(connection.open(connection.MEMORY)) as ctx.db:
            scan(ctx)
            result = list(selector.select_albums(ctx.db, [], [], False))
            assert result[0].tracks[0].pictures[0].mismatch
            result = CheckFlacPictureMetadata(ctx).check(result[0])
            assert result is not None
            assert result.message == "embedded image metadata mismatch on 1 tracks, example image/png 400x400 but container says image/jpeg 399x399"
            assert result.fixer
            assert result.fixer.option_automatic_index is not None
            assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

            scan(ctx)
            result = list(selector.select_albums(ctx.db, [], [], False))
            assert len(result[0].tracks[0].pictures) == 1
            assert not result[0].tracks[0].pictures[0].mismatch
            assert result[0].tracks[0].pictures[0].format == "image/png"
            assert result[0].tracks[0].pictures[0].width == 400
            assert result[0].tracks[0].pictures[0].height == 400
            result = CheckFlacPictureMetadata(ctx).check(result[0])
            assert result is None
