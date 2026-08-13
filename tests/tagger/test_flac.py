import os

import pytest
import xxhash
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture

from albums.entities import Album, Track, TrackPicture
from albums.picture import PictureInfo
from albums.tagger import AlbumTagger, BasicField, Picture, PictureType

from ..fixtures.create_library import create_library, make_image_data

track1 = Track(
    filename="1.flac",
    pictures=[
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
    ],
)
track2 = Track(
    filename="2.flac",
    pictures=[
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
        TrackPicture(picture_info=PictureInfo("image/jpeg", 300, 300, 24, 1, b""), picture_type=PictureType.COVER_BACK),
    ],
)
track3 = Track(
    filename="3.flac",
    tag={BasicField.ORGANIZATION: "ABC", BasicField.ALBUMARTIST: "foo artist", BasicField.DISCTOTAL: "2"},
    legacy_fields=["label", "album artist", "totaldiscs"],
)

album = Album(path="bar" + os.sep, tracks=[track1, track2, track3])


class TestFlac:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestFlac.library = create_library("tagger_flac", [album])
        TestFlac.tagger = AlbumTagger(TestFlac.library / album.path)

    def test_read_flac_picture(self):
        with TestFlac.tagger.open(track1.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
        assert len(pictures) == 1

        assert pictures[0].type == PictureType.COVER_FRONT
        assert pictures[0].picture_info.mime_type == "image/png"
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400
        assert pictures[0].picture_info.load_issue == ()

    def test_read_flac_two_pictures(self):
        with TestFlac.tagger.open(track2.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
        assert len(pictures) == 2
        assert pictures[0].type == PictureType.COVER_FRONT
        assert pictures[0].picture_info.mime_type == "image/png"
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400

        assert pictures[1].type == PictureType.COVER_BACK
        assert pictures[1].picture_info.mime_type == "image/jpeg"
        assert pictures[1].picture_info.width == pictures[1].picture_info.height == 300

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
            pictures = [pic for (pic, _) in file.get_pictures()]
        assert len(pictures) == 1
        assert pictures[0].picture_info.mime_type == "image/png"
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400
        assert pictures[0].picture_info.load_issue == (("format", "image/jpeg"), ("width", 401), ("height", 401))

    def test_remove_only_flac_pic(self):
        with TestFlac.tagger.open(track1.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert pictures[0].type == PictureType.COVER_FRONT
        assert pictures[0].picture_info.mime_type == "image/png"
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400

        with TestFlac.tagger.open(track1.filename) as file:
            file.remove_picture(pictures[0])

        with TestFlac.tagger.open(track1.filename) as file:
            assert list(file.get_pictures()) == []

    def test_remove_one_flac_pic(self):
        with TestFlac.tagger.open(track2.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert pictures[0].type == track2.pictures[0].picture_type
        assert pictures[0].picture_info.mime_type == track2.pictures[0].picture_info.mime_type
        assert (
            pictures[0].picture_info.width
            == pictures[0].picture_info.height
            == track2.pictures[0].picture_info.height
            == track2.pictures[0].picture_info.width
        )
        front = pictures[0]

        assert pictures[1].type == track2.pictures[1].picture_type
        assert pictures[1].picture_info.mime_type == track2.pictures[1].picture_info.mime_type
        assert (
            pictures[1].picture_info.width
            == pictures[1].picture_info.height
            == track2.pictures[1].picture_info.height
            == track2.pictures[1].picture_info.width
        )
        back = pictures[1]

        with TestFlac.tagger.open(track2.filename) as file:
            file.remove_picture(front)

        with TestFlac.tagger.open(track2.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert pictures == [back]

    def test_replace_one_flac_pic(self):
        with TestFlac.tagger.open(track2.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
        assert pictures[0].type == track2.pictures[0].picture_type
        front = pictures[0]
        assert pictures[1].type == track2.pictures[1].picture_type
        back = pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        pic_info = PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data))
        replacement = Picture(pic_info, PictureType.FISH, "")
        with TestFlac.tagger.open(track2.filename) as file:
            file.remove_picture(front)
            file.add_picture(replacement, image_data)

        with TestFlac.tagger.open(track2.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
        assert set(pictures) == {back, replacement}

    def test_get_legacy_fields_empty(self):
        with TestFlac.tagger.open(track1.filename) as file:
            legacy = file.get_legacy_fields()
        assert legacy == ()

    def test_get_legacy_fields_present(self):
        with TestFlac.tagger.open(track3.filename) as file:
            legacy = file.get_legacy_fields()

        expected = (
            ("album artist", BasicField.ALBUMARTIST),
            ("label", BasicField.ORGANIZATION),
            ("totaldiscs", BasicField.DISCTOTAL),
        )
        assert sorted(legacy) == sorted(expected)

    def test_get_fields_legacy_mapping(self):
        with TestFlac.tagger.open(track3.filename) as file:
            fields = dict(file.get_fields())

        assert fields[BasicField.ORGANIZATION] == ("ABC",)
        assert fields[BasicField.ALBUMARTIST] == ("foo artist",)
        assert fields[BasicField.DISCTOTAL] == ("2",)
