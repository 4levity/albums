import os

import pytest
import xxhash

from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import Picture, PictureType
from albums.types import Album, Track, TrackPicture

from ..fixtures.create_library import create_library, make_image_data

track = Track(
    filename="1.aiff",
    tag={
        BasicTag.ARTIST: "A",
        BasicTag.TITLE: "T",
        BasicTag.ALBUM: "baz",
        BasicTag.ALBUMARTIST: "baz+foo",
        BasicTag.TRACKNUMBER: "1",
        BasicTag.TRACKTOTAL: "3",
        BasicTag.DISCNUMBER: "2",
        BasicTag.DISCTOTAL: "2",
        BasicTag.GENRE: "Rock",
        BasicTag.ORGANIZATION: "ABC",
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
            tags = dict(file.get_tags())
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
        track_tags = track.tag_dict()
        assert tags[BasicTag.ARTIST] == tuple(track_tags[BasicTag.ARTIST])
        assert tags[BasicTag.ALBUMARTIST] == tuple(track_tags[BasicTag.ALBUMARTIST])
        assert tags[BasicTag.ALBUM] == tuple(track_tags[BasicTag.ALBUM])
        assert tags[BasicTag.TITLE] == tuple(track_tags[BasicTag.TITLE])
        assert tags[BasicTag.GENRE] == tuple(track_tags[BasicTag.GENRE])
        assert tags[BasicTag.ORGANIZATION] == tuple(track_tags[BasicTag.ORGANIZATION])

    def test_update_aiff_tags(self):
        TestAiff.tagger.set_basic_tags(
            TestAiff.library / album.path / track.filename,
            [
                (BasicTag.ARTIST, "a1"),
                (BasicTag.ALBUMARTIST, "a2"),
                (BasicTag.ALBUM, "a3"),
                (BasicTag.TITLE, "t"),
                (BasicTag.GENRE, "Country"),
                (BasicTag.ORGANIZATION, "Q"),
            ],
        )
        with TestAiff.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.ARTIST] == ("a1",)
        assert tags[BasicTag.ALBUMARTIST] == ("a2",)
        assert tags[BasicTag.ALBUM] == ("a3",)
        assert tags[BasicTag.TITLE] == ("t",)
        assert tags[BasicTag.GENRE] == ("Country",)
        assert tags[BasicTag.ORGANIZATION] == ("Q",)

    def test_write_aiff_tracktotal(self):
        with TestAiff.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, "02")
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "3")
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("3",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        # write both at once
        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "2")
            file.set_tag(BasicTag.TRACKTOTAL, "3")
        with TestAiff.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        # remove total
        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, None)
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert BasicTag.TRACKTOTAL not in tags

    def test_write_aiff_disctotal(self):
        with TestAiff.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, "1")
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "1")
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("1",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        # write both at once
        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "2")
            file.set_tag(BasicTag.DISCTOTAL, "2")
        with TestAiff.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        # remove total
        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, None)
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert BasicTag.DISCTOTAL not in tags

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
