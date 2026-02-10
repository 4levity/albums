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
        assert result.message == "album does not have a COVER_FRONT picture"

    def test_front_cover_multiple_front_in_track(self):
        pictures = [
            Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"1111"),
            Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"2222"),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), pictures)])
        result = CheckFrontCoverSelection(Context()).check(album)
        assert result is not None
        assert "COVER_FRONT pictures are not all the same" in result.message
        assert "multiple COVER_FRONT pictures in one track" in result.message

    def test_duplicate_front_cover_in_track(self):
        pictures = [
            Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""),
            Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""),
        ]
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), pictures)])
        result = CheckFrontCoverSelection(Context()).check(album)
        assert result is not None
        assert "duplicate COVER_FRONT pictures in one track" in result.message

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

    def test_front_cover_duplicate_files(self, mocker):
        pic = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")
        picture_files = {"folder.png": pic, "cover.png": pic}
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [pic])], [], [], picture_files)
        result = CheckFrontCoverSelection(Context()).check(album)
        assert result is not None
        assert result.message == "same image data in multiple files: cover.png, folder.png"
        assert result.fixer
        assert result.fixer.options == ["cover.png", "folder.png"]
        assert result.fixer.option_automatic_index == 0

        mock_unlink = mocker.patch("albums.checks.check_front_cover_selection.unlink")
        fix_result = result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert fix_result
        assert mock_unlink.call_args_list == [call(Path(album.path) / "folder.png")]
