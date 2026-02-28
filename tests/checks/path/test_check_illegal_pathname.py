import os

from albums.app import Context
from albums.checks.path.check_illegal_pathname import CheckIllegalPathname
from albums.picture.info import PictureInfo
from albums.tagger.types import Picture, PictureType
from albums.types import Album, PathCompatibilityOption, PictureFile, Track


class TestCheckIllegalPathname:
    def test_pathname_ok(self):
        album = Album(
            "Foo" + os.sep,
            [Track("normal.flac")],
            [],
            [],
            {"normal.jpg": PictureFile(Picture(PictureInfo("image/png", 1, 1, 24, 1, b""), PictureType.OTHER, "", ()), 0, False)},
        )
        assert not CheckIllegalPathname(Context()).check(album)

    def test_pathname_reserved_name_universal(self):
        result = CheckIllegalPathname(Context()).check(Album("Foo" + os.sep, [Track(":.flac")]))
        assert result is not None
        assert "':' is a reserved name" in result.message
        assert "platform=universal" in result.message

    def test_pathname_reserved_character_universal(self):
        result = CheckIllegalPathname(Context()).check(Album("Foo" + os.sep, [Track("a/b.flac")]))
        assert result is not None
        assert "invalid characters found: invalids=('/')" in result.message
        assert "platform=universal" in result.message

    def test_pathname_reserved_name_Windows(self):
        result = CheckIllegalPathname(Context()).check(Album("Foo" + os.sep, [Track("CON.flac")]))
        assert result is not None
        assert "'CON' is a reserved name" in result.message
        assert "platform=universal" in result.message

    def test_pathname_reserved_character_Windows(self):
        result = CheckIllegalPathname(Context()).check(Album("Foo" + os.sep, [Track("a:b.flac")]))
        assert result is not None
        assert "invalid characters found: invalids=(':')" in result.message
        # not sure why pathvalidate reports this as "Windows" when platform="universal", while CON.flac validation reports as "universal"?
        assert "platform=Windows" in result.message

    def test_pathname_ok_Linux(self):
        ctx = Context()
        ctx.config.path_compatibility = PathCompatibilityOption.LINUX
        assert not CheckIllegalPathname(ctx).check(Album("Foo" + os.sep, [Track(":.flac")]))

    def test_pathname_reserved_character_Linux(self):
        ctx = Context()
        ctx.config.path_compatibility = PathCompatibilityOption.LINUX
        result = CheckIllegalPathname(ctx).check(Album("Foo" + os.sep, [Track("a/b.flac")]))
        assert result is not None
        assert "invalid characters found: invalids=('/')" in result.message
        assert "platform=universal" in result.message
