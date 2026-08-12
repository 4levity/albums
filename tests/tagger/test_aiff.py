import os

import pytest
import xxhash

from albums.entities import Album, Track, TrackPicture
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicField
from albums.tagger.types import Picture, PictureType

from ..fixtures.create_library import create_library, make_image_data

track = Track(
    filename="1.aiff",
    tag={
        BasicField.ARTIST: "A",
        BasicField.TITLE: "T",
        BasicField.ALBUM: "baz",
        BasicField.ALBUMARTIST: "baz+foo",
        BasicField.TRACKNUMBER: "1",
        BasicField.TRACKTOTAL: "3",
        BasicField.DISCNUMBER: "2",
        BasicField.DISCTOTAL: "2",
        BasicField.GENRE: "Rock",
        BasicField.ORGANIZATION: "ABC",
    },
    pictures=[
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT, description=""),
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK, description=""),
    ],
)
album = Album(path="baz" + os.sep, tracks=[track])


class TestAiff:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestAiff.library = create_library("tagger_aiff", [album])
        TestAiff.tagger = AlbumTagger(TestAiff.library / album.path)

    def test_read_write_aiff_tags(self):
        with TestAiff.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            fields = dict(file.get_fields())
        assert len(pictures) == 2
        assert any(pic.description.endswith(" ") for pic in pictures)  # aiff frame hash was made unique by modifying description
        assert pictures[0].type == PictureType.COVER_FRONT or pictures[1].type == PictureType.COVER_FRONT
        assert pictures[0].type == PictureType.COVER_BACK or pictures[1].type == PictureType.COVER_BACK
        assert (
            pictures[0].picture_info.width
            == pictures[0].picture_info.height
            == pictures[1].picture_info.width
            == pictures[1].picture_info.height
            == 400
        )
        assert pictures[0].picture_info.mime_type == pictures[1].picture_info.mime_type == "image/png"
        track_fields = track.field_dict()
        assert fields[BasicField.ARTIST] == tuple(track_fields[BasicField.ARTIST])
        assert fields[BasicField.ALBUMARTIST] == tuple(track_fields[BasicField.ALBUMARTIST])
        assert fields[BasicField.ALBUM] == tuple(track_fields[BasicField.ALBUM])
        assert fields[BasicField.TITLE] == tuple(track_fields[BasicField.TITLE])
        assert fields[BasicField.GENRE] == tuple(track_fields[BasicField.GENRE])
        assert fields[BasicField.ORGANIZATION] == tuple(track_fields[BasicField.ORGANIZATION])

    def test_update_aiff_tags(self):
        TestAiff.tagger.set_basic_fields(
            TestAiff.library / album.path / track.filename,
            [
                (BasicField.ARTIST, "a1"),
                (BasicField.ALBUMARTIST, "a2"),
                (BasicField.ALBUM, "a3"),
                (BasicField.TITLE, "t"),
                (BasicField.GENRE, "Country"),
                (BasicField.ORGANIZATION, "Q"),
            ],
        )
        with TestAiff.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.ARTIST] == ("a1",)
        assert fields[BasicField.ALBUMARTIST] == ("a2",)
        assert fields[BasicField.ALBUM] == ("a3",)
        assert fields[BasicField.TITLE] == ("t",)
        assert fields[BasicField.GENRE] == ("Country",)
        assert fields[BasicField.ORGANIZATION] == ("Q",)

    def test_write_aiff_tracktotal(self):
        with TestAiff.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, "02")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("02",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "3")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("3",)
        assert fields[BasicField.TRACKTOTAL] == ("02",)

        # write both at once
        with TestAiff.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "2")
            file.set_field(BasicField.TRACKTOTAL, "3")
        with TestAiff.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        # remove total
        with TestAiff.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert BasicField.TRACKTOTAL not in fields

    def test_write_aiff_disctotal(self):
        with TestAiff.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCTOTAL, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("1",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        # write both at once
        with TestAiff.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "2")
            file.set_field(BasicField.DISCTOTAL, "2")
        with TestAiff.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        # remove total
        with TestAiff.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert BasicField.DISCTOTAL not in fields

    def test_remove_one_aiff_pic(self):
        with TestAiff.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert len(pictures) == 2
        assert pictures[0].type == PictureType.COVER_FRONT
        assert pictures[1].type == PictureType.COVER_BACK
        assert (
            pictures[0].picture_info.width
            == pictures[0].picture_info.height
            == pictures[1].picture_info.width
            == pictures[1].picture_info.height
            == 400
        )
        assert pictures[0].picture_info.mime_type == pictures[1].picture_info.mime_type == "image/png"

        with TestAiff.tagger.open(track.filename) as file:
            file.remove_picture(pictures[0])
        with TestAiff.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert len(pictures) == 1
        assert pictures[0].type == PictureType.COVER_BACK
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400
        assert pictures[0].picture_info.mime_type == "image/png"

    def test_replace_one_aiff_pic(self):
        with TestAiff.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
        assert len(pictures) == 2
        assert pictures[0].type == PictureType.COVER_FRONT
        front = pictures[0]
        assert pictures[1].type == PictureType.COVER_BACK
        back = pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        replacement = Picture(PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data)), PictureType.FISH, "")

        with TestAiff.tagger.open(track.filename) as file:
            file.remove_picture(front)
            file.add_picture(replacement, image_data)

        with TestAiff.tagger.open(track.filename) as file:
            assert set(pic for (pic, _) in file.get_pictures()) == {replacement, back}
