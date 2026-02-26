import os

import pytest
import xxhash
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture

from albums.tagger.folder import AlbumTagger
from albums.tagger.types import AlbumPicture, PictureInfo
from albums.types import Album, Picture, PictureType, Track

from ..fixtures.create_library import create_library, make_image_data

track1 = Track("1.flac", {}, 0, 0, None, [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")])
track2 = Track(
    "2.flac",
    {},
    0,
    0,
    None,
    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/jpeg", 300, 300, 0, b"")],
)
album = Album("bar" + os.sep, [track1, track2])


class TestFlac:
    @pytest.fixture(scope="function", autouse=True)
    def setup_cli_tests(self):
        TestFlac.library = create_library("tagger_flac", [album])
        TestFlac.tagger = AlbumTagger(TestFlac.library / album.path)

    def test_read_flac_picture(self):
        with TestFlac.tagger.open(track1.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 1

        assert scan.pictures[0].picture_type == PictureType.COVER_FRONT
        assert scan.pictures[0].file_info.mime_type == "image/png"
        assert scan.pictures[0].file_info.width == scan.pictures[0].file_info.height == 400
        assert scan.pictures[0].load_issue == ()

    def test_read_flac_two_pictures(self):
        with TestFlac.tagger.open(track2.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 2
        assert scan.pictures[0].picture_type == PictureType.COVER_FRONT
        assert scan.pictures[0].file_info.mime_type == "image/png"
        assert scan.pictures[0].file_info.width == scan.pictures[0].file_info.height == 400

        assert scan.pictures[1].picture_type == PictureType.COVER_BACK
        assert scan.pictures[1].file_info.mime_type == "image/jpeg"
        assert scan.pictures[1].file_info.width == scan.pictures[1].file_info.height == 300

    def test_read_flac_picture_mismatch(self):
        file = TestFlac.library / album.path / track1.filename
        mut = FLAC(file)
        mut.clear_pictures()
        pic = FlacPicture()
        pic.data = make_image_data(400, 400, "PNG")
        pic.type = PictureType.COVER_FRONT
        pic.mime = "image/jpeg"  # wrong
        pic.width = 401  # wrong
        pic.height = 401  # wrong
        pic.depth = 8
        mut.add_picture(pic)
        mut.save()

        with TestFlac.tagger.open(track1.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 1
        assert scan.pictures[0].file_info.mime_type == "image/png"
        assert scan.pictures[0].file_info.width == scan.pictures[0].file_info.height == 400
        assert scan.pictures[0].load_issue == (("format", "image/jpeg"), ("width", 401), ("height", 401))

    def test_remove_only_flac_pic(self):
        with TestFlac.tagger.open(track1.filename) as file:
            scan = file.scan()

        assert scan.pictures[0].picture_type == PictureType.COVER_FRONT
        assert scan.pictures[0].file_info.mime_type == "image/png"
        assert scan.pictures[0].file_info.width == scan.pictures[0].file_info.height == 400

        with TestFlac.tagger.open(track1.filename) as file:
            file.remove_picture(scan.pictures[0])

        with TestFlac.tagger.open(track1.filename) as file:
            scan = file.scan()
        assert scan.pictures == ()

    def test_remove_one_flac_pic(self):
        with TestFlac.tagger.open(track2.filename) as file:
            scan = file.scan()

        assert scan.pictures[0].picture_type == track2.pictures[0].picture_type
        assert scan.pictures[0].file_info.mime_type == track2.pictures[0].format
        assert scan.pictures[0].file_info.width == scan.pictures[0].file_info.height == track2.pictures[0].height == track2.pictures[0].width
        front = scan.pictures[0]

        assert scan.pictures[1].picture_type == track2.pictures[1].picture_type
        assert scan.pictures[1].file_info.mime_type == track2.pictures[1].format
        assert scan.pictures[1].file_info.width == scan.pictures[1].file_info.height == track2.pictures[1].height == track2.pictures[1].width
        back = scan.pictures[1]

        with TestFlac.tagger.open(track2.filename) as file:
            file.remove_picture(front)

        with TestFlac.tagger.open(track2.filename) as file:
            scan = file.scan()

        assert scan.pictures == (back,)

    def test_replace_one_flac_pic(self):
        with TestFlac.tagger.open(track2.filename) as file:
            scan = file.scan()
        assert scan.pictures[0].picture_type == track2.pictures[0].picture_type
        front = scan.pictures[0]
        assert scan.pictures[1].picture_type == track2.pictures[1].picture_type
        back = scan.pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        pic_info = PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data))
        replacement = AlbumPicture(pic_info, PictureType.FISH, "", ())
        with TestFlac.tagger.open(track2.filename) as file:
            file.remove_picture(front)
            file.add_picture(replacement, image_data)

        with TestFlac.tagger.open(track2.filename) as file:
            scan = file.scan()
        assert set(scan.pictures) == {back, replacement}
