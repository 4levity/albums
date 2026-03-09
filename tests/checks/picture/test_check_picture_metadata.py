import os

from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from sqlalchemy import select
from sqlalchemy.orm import Session

from albums.app import Context
from albums.checks.picture.check_picture_metadata import CheckPictureMetadata
from albums.database import connection
from albums.database.models import AlbumEntity
from albums.database.operations import album_to_album
from albums.library.scanner import scan
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import Picture, PictureType, StreamInfo
from albums.types import Album, BasicTag, PictureFile, Track

from ...fixtures.create_library import create_library, make_image_data


class TestCheckPictureMetadata:
    def test_picture_metadata_ok(self):
        pic = Picture(PictureInfo("image/png", 1, 1, 1, 0, b""), PictureType.COVER_FRONT, "")
        album = Album(
            "", [Track("1.flac", {}, 0, 0, StreamInfo(1, 0, 0, "FLAC"), [pic])], [], [], [PictureFile("cover.png", pic.picture_info, 999, False)]
        )
        result = CheckPictureMetadata(Context()).check(album)
        assert result is None

    def test_picture_metadata_mismatch(self):
        load_issue = (("format", "image/jpeg"), ("width", 0), ("height", 0))
        pic = Picture(PictureInfo("image/png", 400, 400, 24, 0, b"", load_issue), PictureType.COVER_FRONT, "")
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [pic])])
        result = CheckPictureMetadata(Context()).check(album)
        assert result is not None
        assert result.message == "embedded image metadata mismatch on 1 tracks, example image/png 400x400 but container says image/jpeg 0x0"
        assert result.fixer

    def test_picture_metadata_mismatch_fix_flac(self):
        album = Album("foo", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"))])
        ctx = Context()
        ctx.config.library = create_library("picture_metadata_flac", [album])
        file = ctx.config.library / album.path / album.tracks[0].filename
        flac = FLAC(file)
        pic = FlacPicture()
        pic.data = make_image_data(width=400, height=400, format="PNG")
        pic.type = PictureType.COVER_FRONT
        pic.mime = "image/jpeg"
        pic.width = 399
        pic.height = 399
        pic.depth = 1
        flac.add_picture(pic)
        flac.save()

        ctx.db = connection.open(connection.MEMORY)
        try:
            scan(ctx)
            with Session(ctx.db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert result.tracks[0].pictures[0].picture_info.load_issue

                result = CheckPictureMetadata(ctx).check(album_to_album(result))
            assert result is not None
            assert result.message == "embedded image metadata mismatch on 1 tracks, example image/png 400x400 but container says image/jpeg 399x399"
            assert result.fixer
            assert result.fixer.option_automatic_index is not None
            assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

            scan(ctx, reread=True)
            with Session(ctx.db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert len(result.tracks[0].pictures) == 1
                assert not result.tracks[0].pictures[0].picture_info.load_issue
                assert result.tracks[0].pictures[0].picture_info.mime_type == "image/png"
                assert result.tracks[0].pictures[0].picture_info.width == 400
                assert result.tracks[0].pictures[0].picture_info.height == 400
                result = CheckPictureMetadata(ctx).check(album_to_album(result))
                assert result is None
        finally:
            ctx.db.dispose()

    def test_picture_metadata_mismatch_fix_mp3(self):
        album = Album("foo", [Track("1.mp3", {BasicTag.TITLE: ["1"]}, 0, 0, StreamInfo(1.5, 0, 0, "MP3"))])
        ctx = Context()
        ctx.config.library = create_library("picture_metadata_mp3", [album])

        tagger = AlbumTagger(ctx.config.library / album.path)
        image_data = make_image_data(width=400, height=400, format="PNG")
        pic_scan = tagger.get_picture_scanner().scan(image_data)
        # wrong mime type:
        pic_info = PictureInfo("image/jpeg", 400, 400, 24, pic_scan.file_size, pic_scan.file_hash, pic_scan.load_issue)
        with tagger.open(album.tracks[0].filename) as tags:
            tags.add_picture(Picture(pic_info, PictureType.COVER_FRONT, ""), image_data)

        ctx.db = connection.open(connection.MEMORY)
        try:
            scan(ctx)
            with Session(ctx.db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert result.tracks[0].pictures[0].picture_info.load_issue
                result = CheckPictureMetadata(ctx).check(album_to_album(result))
            assert result is not None
            assert result.message == "embedded image metadata mismatch on 1 tracks, example image/png 400x400 but container says image/jpeg"
            assert result.fixer
            assert result.fixer.option_automatic_index is not None
            assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

            scan(ctx, reread=True)
            with Session(ctx.db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                assert len(result.tracks[0].pictures) == 1
                assert not result.tracks[0].pictures[0].picture_info.load_issue
                assert result.tracks[0].pictures[0].picture_info.mime_type == "image/png"
                assert result.tracks[0].pictures[0].picture_info.width == 400
                assert result.tracks[0].pictures[0].picture_info.height == 400
                result = CheckPictureMetadata(ctx).check(album_to_album(result))
            assert result is None
        finally:
            ctx.db.dispose()

    def test_picture_image_file_extension_mismatch(self):
        pic = Picture(PictureInfo("image/png", 1, 1, 1, 0, b""), PictureType.COVER_FRONT, "")
        track = Track("1.flac", {}, 0, 0, StreamInfo(1, 0, 0, "FLAC"), [pic])
        album = Album("foo" + os.sep, [track], [], [], [PictureFile("cover.png", pic.picture_info, 1, False)])
        ctx = Context()
        ctx.config.library = create_library("picture_metadata_file_ext", [album])
        os.rename(ctx.config.library / album.path / "cover.png", ctx.config.library / album.path / "cover.gif")
        ctx.db = connection.open(connection.MEMORY)
        try:
            scan(ctx)
            with Session(ctx.db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                gif = next(file for file in result.picture_files if file.filename == "cover.gif")
                assert gif.picture_info.mime_type == "image/png"
                assert gif.picture_info.load_issue == (("format", "image/gif"),)

                result = CheckPictureMetadata(ctx).check(album_to_album(result))
            assert result is not None
            assert result.message == "image files with wrong extension, example cover.gif should be cover.png"
            assert result.fixer
            assert result.fixer.option_automatic_index is not None
            assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

            scan(ctx, reread=True)
            with Session(ctx.db) as session:
                result = session.execute(select(AlbumEntity)).tuples().one()[0]
                png = next(file for file in result.picture_files if file.filename == "cover.png")
                assert png.picture_info.mime_type == "image/png"
                assert png.picture_info.load_issue == ()
                result = CheckPictureMetadata(ctx).check(album_to_album(result))
            assert result is None
        finally:
            ctx.db.dispose()
