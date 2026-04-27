import os
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import call, mock_open, patch

from albums.app import Context
from albums.checks.picture.check_cover_available import CheckCoverAvailable
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import PictureType, TaggerFile
from albums.types import Album, FixResult, PictureFile, Track, TrackPicture

from ...fixtures.create_library import make_image_data


class TestCheckCoverAvailable:
    def test_cover_missing_ok(self):
        album = Album(path="", tracks=[Track(filename="1.flac"), Track(filename="2.flac")])
        assert not CheckCoverAvailable(Context()).check(album)

    def test_cover_missing_required(self, mocker):
        mocker.patch("albums.checks.picture.check_cover_available.which", return_value=None)  # test behavior doesn't change if sacad is installed
        album = Album(path="", tracks=[Track(filename="1.flac"), Track(filename="2.flac")])
        ctx = Context()
        ctx.config.checks[CheckCoverAvailable.name]["cover_required"] = True
        result = CheckCoverAvailable(ctx).check(album)
        assert result is not None
        assert "album does not have any pictures to use as cover art, and cannot search" in result.message

    def test_album_pictures_but_no_front_cover(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK)],
                ),
                Track(
                    filename="2.flac",
                    pictures=[TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK)],
                ),
            ],
        )
        result = CheckCoverAvailable(Context()).check(album)
        assert result is not None
        assert "album has pictures but none is COVER_FRONT picture" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["1.flac (and 1 more) image/png COVER_BACK"]
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        image_data = make_image_data()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_get_image_data = mocker.patch.object(tagger, "get_image_data", return_value=image_data)

        m_open = mock_open()
        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_get_image_data.call_count == 1
        m_open.assert_has_calls(
            [
                call(Path(".") / album.path / "cover.png", "wb"),
                call().__enter__(),
                call().write(image_data),
                call().__exit__(None, None, None),
            ],
        )

    def test_album_picture_files_no_front_cover(self, mocker):
        album = Album(
            path="",
            tracks=[Track(filename="1.flac"), Track(filename="2.flac")],
            picture_files=[PictureFile(filename="other.png", picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""))],
        )
        result = CheckCoverAvailable(Context()).check(album)
        assert result is not None
        assert "album has pictures but none is COVER_FRONT picture" in result.message

        assert result.fixer is not None
        assert result.fixer.options == ["other.png image/png OTHER"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.picture.check_cover_available.rename")
        result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_rename.call_args_list == [call(Path(".") / album.path / "other.png", Path(".") / album.path / "cover.png")]

    def test_no_cover_prefer_rename(self, mocker):
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.OTHER)],
                ),
                Track(
                    filename="2.flac",
                    pictures=[TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.OTHER)],
                ),
            ],
            picture_files=[PictureFile(filename="other.png", picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""))],
        )
        result = CheckCoverAvailable(Context()).check(album)
        assert result is not None
        assert "album has pictures but none is COVER_FRONT picture" in result.message

        assert result.fixer is not None
        assert result.fixer.options == ["1.flac (and 2 more) image/png OTHER"]
        assert result.fixer.option_automatic_index == 0

        # same image was found embedded and in other.png - rename other.png instead of creating new cover.png
        mock_rename = mocker.patch("albums.checks.picture.check_cover_available.rename")
        result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_rename.call_args_list == [call(Path(".") / album.path / "other.png", Path(".") / album.path / "cover.png")]

    def test_cover_art_downloader(self, mocker):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={"artist": "Foo", "album": "Bar"})])
        ctx = Context()
        ctx.config.checks[CheckCoverAvailable.name]["cover_required"] = True

        mock_which = mocker.patch("albums.checks.picture.check_cover_available.which", return_value="truthy")
        result = CheckCoverAvailable(ctx).check(album)
        assert mock_which.call_count == 2  # checks for sacad and sacad_r
        assert result is not None
        assert result.message == "album does not have any pictures to use as cover art, can try searching"
        assert result.fixer is not None
        assert len(result.fixer.options) == 1
        assert ">> Try to retrieve cover image with: sacad" in result.fixer.options[0]
        assert result.fixer.option_automatic_index == 0

        mock_iglob = mocker.patch("albums.checks.picture.check_cover_available.iglob")
        mock_iglob.side_effect = [(), ("cover.jpg",)]
        mock_run = mocker.patch("albums.checks.picture.check_cover_available.run", return_value=CompletedProcess([], 0))

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index]) == FixResult.CHANGED_ALBUM

        assert mock_iglob.call_count == 2
        expect_cmd = ["sacad", "--preserve-format", "--size-tolerance", "60", "Foo", "Bar", "1200", "cover.png"]
        assert mock_run.call_args_list == [call(expect_cmd, cwd=Path(album.path))]

    def test_cover_art_downloader_fails(self, mocker):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac", tag={"artist": "Foo", "album": "Bar"})])
        ctx = Context()
        ctx.config.checks[CheckCoverAvailable.name]["cover_required"] = True

        mocker.patch("albums.checks.picture.check_cover_available.which", return_value="truthy")
        result = CheckCoverAvailable(ctx).check(album)
        assert result is not None
        assert result.message == "album does not have any pictures to use as cover art, can try searching"
        assert result.fixer is not None
        assert len(result.fixer.options) == 1
        assert ">> Try to retrieve cover image with: sacad" in result.fixer.options[0]
        assert result.fixer.option_automatic_index == 0

        mock_iglob = mocker.patch("albums.checks.picture.check_cover_available.iglob")
        mock_iglob.side_effect = [(), ()]
        mock_run = mocker.patch("albums.checks.picture.check_cover_available.run", return_value=CompletedProcess([], 1))

        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index]) == FixResult.NO_CHANGE

        assert mock_iglob.call_count == 2
        expect_cmd = ["sacad", "--preserve-format", "--size-tolerance", "60", "Foo", "Bar", "1200", "cover.png"]
        assert mock_run.call_args_list == [call(expect_cmd, cwd=Path(album.path))]
