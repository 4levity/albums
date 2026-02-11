from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_front_cover_selection import CheckFrontCoverSelection
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckFrontCoverSelection:
    def test_front_cover_ok(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
                ),
                Track(
                    "2.flac",
                    {},
                    0,
                    0,
                    Stream(1.5, 0, 0, "FLAC"),
                    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
                ),
            ],
        )
        assert not CheckFrontCoverSelection(Context()).check(album)

    def test_front_cover_missing_ok(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))])
        assert not CheckFrontCoverSelection(Context()).check(album)

    def test_front_cover_missing_required(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))])
        ctx = Context()
        ctx.config["checks"] = {CheckFrontCoverSelection.name: {"cover_required": True}}
        result = CheckFrontCoverSelection(ctx).check(album)
        assert result is not None
        assert "album does not have a COVER_FRONT picture" in result.message

    def test_front_cover_multiple_unique(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 500, 500, 0, b"")]),
            ],
        )
        result = CheckFrontCoverSelection(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT pictures are not all the same"

    def test_front_cover_multiple_unique_allowed(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 500, 500, 0, b"")]),
            ],
        )
        ctx = Context()
        ctx.config["checks"] = {CheckFrontCoverSelection.name: {"unique": False}}
        result = CheckFrontCoverSelection(ctx).check(album)
        assert result is None

    def test_album_pictures_but_no_front_cover(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")]),
            ],
        )
        result = CheckFrontCoverSelection(Context()).check(album)
        assert result is not None
        assert result.message == "album has pictures but none is COVER_FRONT picture"

    def test_front_cover_inconsistent(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")),
            ],
        )
        result = CheckFrontCoverSelection(Context()).check(album)
        assert result is not None
        assert result.message == "some tracks have COVER_FRONT and some do not"

    def test_has_unmarked_cover_source_file(self, mocker):
        picture_files = {"cover.png": Picture(PictureType.COVER_FRONT, "image/png", 1000, 1000, 10000, b"")}
        album = Album(
            "",
            [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 400, b"")])],
            [],
            [],
            picture_files,
            999,
        )
        ctx = Context()
        ctx.db = True
        result = CheckFrontCoverSelection(ctx).check(album)
        assert result is not None
        assert (
            result.message
            == "multiple cover art images: designate a high-resolution image file as cover art source or delete image files (keep embedded images)"
        )
        assert result.fixer
        assert result.fixer.options == [">> Mark as front cover source: cover.png", ">> Delete all cover image files: cover.png"]
        assert result.fixer.option_automatic_index == 0

        update_picture_files_mock = mocker.patch("albums.checks.check_front_cover_selection.operations.update_picture_files")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert update_picture_files_mock.call_count == 1
        assert update_picture_files_mock.call_args.args[1] == 999
        assert update_picture_files_mock.call_args.args[2]["cover.png"].front_cover_source

    def test_multiple_cover_image_files_no_embedded(self, mocker):
        picture_files = {
            "cover_big.png": Picture(PictureType.COVER_FRONT, "image/png", 1000, 1000, 100000, b"1111"),
            "cover_small.png": Picture(PictureType.COVER_FRONT, "image/png", 1000, 1000, 1000, b"2222"),
        }
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))], [], [], picture_files, 999)
        ctx = Context()
        ctx.db = True
        result = CheckFrontCoverSelection(ctx).check(album)
        assert result is not None
        assert (
            result.message
            == "multiple cover art images: designate a high-resolution image file as cover art source (tracks do not have embedded images)"
        )
        assert result.fixer
        assert result.fixer.options == [">> Mark as front cover source: cover_big.png", ">> Mark as front cover source: cover_small.png"]
        assert result.fixer.option_automatic_index == 0

        update_picture_files_mock = mocker.patch("albums.checks.check_front_cover_selection.operations.update_picture_files")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert update_picture_files_mock.call_count == 1
        assert update_picture_files_mock.call_args.args[1] == 999
        assert update_picture_files_mock.call_args.args[2]["cover_big.png"].front_cover_source

    def test_multiple_cover_image_files_with_cover_source(self, mocker):
        picture_files = {
            "cover_big.png": Picture(PictureType.COVER_FRONT, "image/png", 1000, 1000, 100000, b"1111", None, None, 0, True),
            "cover_small.png": Picture(PictureType.COVER_FRONT, "image/png", 1000, 1000, 1000, b"2222"),
        }
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))], [], [], picture_files, 999)
        ctx = Context()
        ctx.db = True
        result = CheckFrontCoverSelection(ctx).check(album)
        assert result is not None
        assert result.message == "multiple front cover image files, and one of them is marked cover source (delete others)"
        assert result.fixer
        assert result.fixer.options == ['>> Keep cover source image "cover_big.png" and delete other cover files: cover_small.png']
        assert result.fixer.option_automatic_index is None

        mock_unlink = mocker.patch("albums.checks.helpers.unlink")
        fix_result = result.fixer.fix(result.fixer.options[0])
        assert fix_result
        assert mock_unlink.call_args_list == [call(Path(album.path) / "cover_small.png")]
