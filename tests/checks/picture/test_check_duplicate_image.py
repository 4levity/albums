from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_types import FixResult
from albums.checks.picture.check_duplicate_image import CheckDuplicateImage
from albums.entities import Album, PictureFile, Track, TrackPicture
from albums.picture import PictureInfo
from albums.tagger import AlbumTagger, PictureType

from ...helpers import MockTagger, apply_automatic_fix


class TestCheckDuplicateImage:
    def test_duplicate_image_ok(self):
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
        assert not CheckDuplicateImage(Context()).check(album)

    def test_duplicate_image_in_track(self):
        pic_info = PictureInfo("image/png", 400, 400, 24, 1, b"")
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_BACK),
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_BACK),
                    ],
                )
            ],
        )
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert "duplicate embedded image data in one or more files: COVER_BACK" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Remove duplicate embedded images (keep the first)"]
        assert result.fixer.option_automatic_index == 0

    def test_duplicate_image_in_track_fix(self, mocker):
        pic_info = PictureInfo("image/png", 400, 400, 24, 1, b"")
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_BACK),
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_BACK),
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_BACK),
                    ],
                )
            ],
        )
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert result.fixer

        tagger = MockTagger()
        picture = album.tracks[0].pictures[0].to_picture()
        mock_get_pictures = mocker.patch.object(tagger, "get_pictures")
        mock_get_pictures.side_effect = [[(picture, b"data")] * 3]
        mock_remove_picture = mocker.patch.object(tagger, "remove_picture")
        mock_add_picture = mocker.patch.object(tagger, "add_picture")
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger

        assert apply_automatic_fix(result) == FixResult.CHANGED_ALBUM

        assert mock_get_pictures.call_count == 1
        assert mock_remove_picture.call_count == 1
        assert mock_remove_picture.call_args_list[0][0][0] == picture
        assert mock_add_picture.call_count == 1
        assert mock_add_picture.call_args_list[0][0] == (picture, b"data")

    def test_duplicate_image_in_track_read_only(self):
        pic_info = PictureInfo("image/jpeg", 400, 400, 24, 1, b"")
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.wma",
                    pictures=[
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_FRONT),
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_FRONT),
                    ],
                )
            ],
        )
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert "duplicate embedded image data in one or more files: COVER_FRONT" in result.message
        assert "cannot update 1.wma" in result.message
        assert result.fixer is None

    def test_duplicate_image_in_track_mixed(self):
        pic_info = PictureInfo("image/jpeg", 400, 400, 24, 1, b"")
        album = Album(
            path="",
            tracks=[
                Track(
                    filename="1.flac",
                    pictures=[
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_FRONT),
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_FRONT),
                    ],
                ),
                Track(
                    filename="2.wma",
                    pictures=[
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_FRONT),
                        TrackPicture(picture_info=pic_info, picture_type=PictureType.COVER_FRONT),
                    ],
                ),
            ],
        )
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert "duplicate embedded image data in one or more files: COVER_FRONT" in result.message
        assert "cannot update 2.wma" in result.message
        # the flac file can still be fixed, the wma file is reported
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

    def test_cover_duplicate_files(self, mocker):
        pic = TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT)
        album = Album(
            path="",
            tracks=[Track(filename="1.flac", pictures=[pic])],
            picture_files=[
                PictureFile(filename="folder.png", picture_info=pic.picture_info),
                PictureFile(filename="cover.png", picture_info=pic.picture_info),
            ],
        )
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert result.message == "same image data in multiple files: cover.png, folder.png"
        assert result.fixer
        assert result.fixer.options == ["cover.png", "folder.png"]

        mock_unlink = mocker.patch("albums.checks.helpers.unlink")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_unlink.call_args_list == [call(Path(album.path) / "folder.png")]

    def test_other_type_duplicate_files(self, mocker):
        pic_info = PictureInfo("image/png", 400, 400, 24, 1, b"")
        album = Album(
            path="",
            picture_files=[
                PictureFile(filename="extra-long-name.png", picture_info=pic_info),
                PictureFile(filename="art.png", picture_info=pic_info),
            ],
        )
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert result.message == "same image data in multiple files: art.png, extra-long-name.png"
        assert result.fixer
        assert result.fixer.options == ["art.png", "extra-long-name.png"]

        mock_unlink = mocker.patch("albums.checks.helpers.unlink")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_unlink.call_args_list == [call(Path(album.path) / "extra-long-name.png")]

    def test_other_type_duplicate_files_cover_only(self):
        pic_info = PictureInfo("image/png", 400, 400, 24, 1, b"")
        album = Album(
            path="",
            picture_files=[
                PictureFile(filename="extra-long-name.png", picture_info=pic_info),
                PictureFile(filename="art.png", picture_info=pic_info),
            ],
        )
        check = CheckDuplicateImage(Context())
        check.cover_only = True
        assert check.check(album) is None

    def test_front_cover_preferred_over_other_types(self, mocker):
        front_info = PictureInfo("image/png", 400, 400, 24, 1, b"front")
        other_info = PictureInfo("image/png", 400, 400, 24, 1, b"other")
        album = Album(
            path="",
            picture_files=[
                PictureFile(filename="z-front.png", picture_info=front_info),
                PictureFile(filename="a-front.png", picture_info=front_info),
                PictureFile(filename="z-art.png", picture_info=other_info),
                PictureFile(filename="a-art.png", picture_info=other_info),
            ],
        )
        # front cover duplicates are reported first, even when other types sort first by filename
        result = CheckDuplicateImage(Context()).check(album)
        assert result is not None
        assert result.message == "same image data in multiple files: a-front.png, z-front.png"
        assert result.fixer
        assert result.fixer.options == ["a-front.png", "z-front.png"]

        mock_unlink = mocker.patch("albums.checks.helpers.unlink")
        fix_result = apply_automatic_fix(result)
        assert fix_result == FixResult.CHANGED_ALBUM
        assert mock_unlink.call_args_list == [call(Path(album.path) / "z-front.png")]
