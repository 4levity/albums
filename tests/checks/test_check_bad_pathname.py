import os

from albums.app import Context
from albums.checks.check_bad_pathname import CheckBadPathname
from albums.types import Album, Picture, PictureType, Track


class TestCheckBadPathname:
    def test_pathname_ok(self):
        album = Album("Foo" + os.sep, [Track("normal.flac")], [], [], {"normal.jpg": Picture(PictureType.OTHER, "image/jpeg", 1, 1, 1, b"")})
        assert not CheckBadPathname(Context()).check(album)

    def test_pathname_duplicate_filename(self):
        album = Album(
            "Foo" + os.sep,
            [Track("normal.flac")],
            [],
            [],
            {
                "FileName.jpg": Picture(PictureType.OTHER, "image/jpeg", 1, 1, 1, b""),
                "Filename.jpg": Picture(PictureType.OTHER, "image/jpeg", 1, 1, 1, b""),
            },
        )
        result = CheckBadPathname(Context()).check(album)
        assert result is not None
        assert "2 files are variations of filename.jpg" in result.message

    def test_pathname_reserved_name_universal(self):
        result = CheckBadPathname(Context()).check(Album("Foo" + os.sep, [Track(":.flac")]))
        assert result is not None
        assert "':' is a reserved name" in result.message
        assert "platform=universal" in result.message

    def test_pathname_reserved_character_universal(self):
        result = CheckBadPathname(Context()).check(Album("Foo" + os.sep, [Track("a/b.flac")]))
        assert result is not None
        assert "invalid characters found: invalids=('/')" in result.message
        assert "platform=universal" in result.message

    def test_pathname_ok_Linux(self):
        ctx = Context()
        ctx.config["checks"] = {CheckBadPathname.name: {"compatibility": "Linux"}}
        assert not CheckBadPathname(ctx).check(Album("Foo" + os.sep, [Track(":.flac")]))

    def test_pathname_reserved_character_Linux(self):
        ctx = Context()
        ctx.config["checks"] = {CheckBadPathname.name: {"compatibility": "Linux"}}
        result = CheckBadPathname(ctx).check(Album("Foo" + os.sep, [Track("a/b.flac")]))
        assert result is not None
        assert "invalid characters found: invalids=('/')" in result.message
        assert "platform=universal" in result.message
