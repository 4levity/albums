import os

import pytest
import xxhash

from albums.entities import Album, OtherFile, Track, TrackPicture
from albums.picture import PictureInfo
from albums.tagger import AlbumTagger, BasicField, Picture, PictureType

from ..fixtures.create_library import create_library, make_image_data

UUID0 = "00000000-0000-0000-0000-000000000000"
UUID1 = "11111111-1111-1111-1111-111111111111"
track1 = Track(
    filename="1.m4a",
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
        BasicField.MUSICBRAINZ_ALBUMID: UUID0,
        BasicField.MUSICBRAINZ_TRACKID: UUID1,
        BasicField.ORGANIZATION: "ABC",
        BasicField.BARCODE: "0123",
        BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY: "US",
    },
    pictures=[
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b"1111"), picture_type=PictureType.COVER_FRONT),
        TrackPicture(
            picture_info=PictureInfo("image/jpeg", 401, 401, 24, 2, b"2222"), picture_type=PictureType.OTHER
        ),  # type ignored, logs a warning
    ],
)
track2 = Track(
    filename="2.mp4",
    tag={
        BasicField.ARTIST: "A",
        BasicField.TITLE: "T",
        BasicField.ALBUM: "baz",
        BasicField.ALBUMARTIST: "baz+foo",
        BasicField.TRACKNUMBER: "2",
        BasicField.TRACKTOTAL: "3",
        BasicField.DISCNUMBER: "2",
        BasicField.DISCTOTAL: "2",
        BasicField.GENRE: "Rock",
        BasicField.MUSICBRAINZ_ALBUMID: UUID0,
        BasicField.MUSICBRAINZ_TRACKID: UUID1,
        BasicField.ORGANIZATION: "ABC",
        BasicField.BARCODE: "0123",
        BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY: "US",
    },
)
video = OtherFile(filename="video.mp4")
album = Album(path="baz" + os.sep, tracks=[track1, track2], other_files=[video])


class TestMp4:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestMp4.library = create_library("tagger_mp3", [album])
        TestMp4.tagger = AlbumTagger(TestMp4.library / album.path)

    def test_read_write_m4a_tag(self):
        with TestMp4.tagger.open(track1.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            fields = dict(file.get_fields())
            assert not file.has_video()
        assert len(pictures) == 2
        assert pictures[0].type == PictureType.COVER_FRONT
        assert pictures[0].picture_info.mime_type == "image/png"
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400
        assert pictures[1].type == PictureType.COVER_FRONT  # always
        assert pictures[1].picture_info.mime_type == "image/jpeg"
        assert pictures[1].picture_info.width == pictures[1].picture_info.height == 401
        track_fields = track1.field_dict()
        assert fields[BasicField.ARTIST] == tuple(track_fields[BasicField.ARTIST])
        assert fields[BasicField.ALBUMARTIST] == tuple(track_fields[BasicField.ALBUMARTIST])
        assert fields[BasicField.ALBUM] == tuple(track_fields[BasicField.ALBUM])
        assert fields[BasicField.TITLE] == tuple(track_fields[BasicField.TITLE])
        assert fields[BasicField.GENRE] == tuple(track_fields[BasicField.GENRE])
        assert fields[BasicField.TRACKNUMBER] == tuple(track_fields[BasicField.TRACKNUMBER])
        assert fields[BasicField.MUSICBRAINZ_ALBUMID] == tuple(track_fields[BasicField.MUSICBRAINZ_ALBUMID])
        assert fields[BasicField.MUSICBRAINZ_TRACKID] == tuple(track_fields[BasicField.MUSICBRAINZ_TRACKID])
        assert fields[BasicField.ORGANIZATION] == tuple(track_fields[BasicField.ORGANIZATION])
        assert fields[BasicField.BARCODE] == tuple(track_fields[BasicField.BARCODE])
        assert fields[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == tuple(track_fields[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY])

    def test_mp4_audio(self):
        with TestMp4.tagger.open(track2.filename) as file:
            fields = dict(file.get_fields())
            assert not file.has_video()
        track_fields = track2.field_dict()
        assert fields[BasicField.TRACKNUMBER] == tuple(track_fields[BasicField.TRACKNUMBER])

    def test_mp4_video(self):
        with TestMp4.tagger.open(video.filename) as file:
            assert file.has_video()
            pictures = [pic for (pic, _) in file.get_pictures()]
            fields = dict(file.get_fields())
            assert len(pictures) == 0
            assert len(fields) == 0
            file.set_field(BasicField.TRACKNUMBER, "3")
            image_data = make_image_data(600, 600, "JPEG")
            pic = Picture(PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data)), PictureType.COVER_FRONT, "")
            file.add_picture(pic, image_data)

        with TestMp4.tagger.open(video.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            assert pictures == [pic]
            assert file.get_fields() == ((BasicField.TRACKNUMBER, ("3",)),)

    def test_update_mp4_tags(self):
        TestMp4.tagger.set_basic_fields(
            TestMp4.library / album.path / track1.filename,
            [
                (BasicField.ARTIST, "a1"),
                (BasicField.ALBUMARTIST, "a2"),
                (BasicField.ALBUM, "a3"),
                (BasicField.TITLE, "t"),
                (BasicField.GENRE, "Country"),
                (BasicField.MUSICBRAINZ_ALBUMID, UUID1),
                (BasicField.MUSICBRAINZ_TRACKID, UUID0),
                (BasicField.ORGANIZATION, "Q"),
                (BasicField.BARCODE, "0000"),
                (BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY, "UK"),
            ],
        )
        with TestMp4.tagger.open(track1.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.ARTIST] == ("a1",)
        assert fields[BasicField.ALBUMARTIST] == ("a2",)
        assert fields[BasicField.ALBUM] == ("a3",)
        assert fields[BasicField.TITLE] == ("t",)
        assert fields[BasicField.GENRE] == ("Country",)
        assert fields[BasicField.MUSICBRAINZ_ALBUMID] == (UUID1,)
        assert fields[BasicField.MUSICBRAINZ_TRACKID] == (UUID0,)
        assert fields[BasicField.ORGANIZATION] == ("Q",)
        assert fields[BasicField.BARCODE] == ("0000",)
        assert fields[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == ("UK",)

    def test_update_mp4_compilation(self):
        with TestMp4.tagger.open(track1.filename) as file:
            fields = dict(file.get_fields())
            assert BasicField.COMPILATION not in fields
            file.set_field(BasicField.COMPILATION, "1")  # normal enable
        with TestMp4.tagger.open(track1.filename) as file:
            fields = dict(file.get_fields())
            assert fields.get(BasicField.COMPILATION) == ("1",)

            file.set_field(BasicField.COMPILATION, None)  # normal disable
        with TestMp4.tagger.open(track1.filename) as file:
            fields = dict(file.get_fields())
            assert BasicField.COMPILATION not in fields

            file.set_field(BasicField.COMPILATION, "anything")
        with TestMp4.tagger.open(track1.filename) as file:
            fields = dict(file.get_fields())
            assert fields.get(BasicField.COMPILATION) == ("1",)  # set to anything = set to 1

    def test_write_mp4_tracktotal(self):
        with TestMp4.tagger.open(track1.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        with TestMp4.tagger.open(track1.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, "02")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("2",)  # tag cannot store leading 0

        with TestMp4.tagger.open(track1.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "3")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("3",)
        assert fields[BasicField.TRACKTOTAL] == ("2",)

        # write both at once
        with TestMp4.tagger.open(track1.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "2")
            file.set_field(BasicField.TRACKTOTAL, "3")
        with TestMp4.tagger.open(track1.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        # remove total
        with TestMp4.tagger.open(track1.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert BasicField.TRACKTOTAL not in fields

    def test_write_mp4_disctotal(self):
        with TestMp4.tagger.open(track1.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        with TestMp4.tagger.open(track1.filename) as file:
            file.set_field(BasicField.DISCTOTAL, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        with TestMp4.tagger.open(track1.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("1",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        # write both at once
        with TestMp4.tagger.open(track1.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "2")
            file.set_field(BasicField.DISCTOTAL, "2")
        with TestMp4.tagger.open(track1.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        # remove total
        with TestMp4.tagger.open(track1.filename) as file:
            file.set_field(BasicField.DISCTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert BasicField.DISCTOTAL not in fields

    def test_remove_one_m4a_pic(self):
        with TestMp4.tagger.open(track1.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert len(pictures) == 2
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400
        assert pictures[0].picture_info.mime_type == "image/png"
        assert pictures[1].picture_info.mime_type == "image/jpeg"

        with TestMp4.tagger.open(track1.filename) as file:
            file.remove_picture(pictures[0])
        with TestMp4.tagger.open(track1.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert len(pictures) == 1
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 401
        assert pictures[0].picture_info.mime_type == "image/jpeg"

    def test_replace_one_m4a_pic(self):
        with TestMp4.tagger.open(track1.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
        assert len(pictures) == 2
        assert pictures[0].picture_info.mime_type == "image/png"
        first = pictures[0]
        assert pictures[1].picture_info.mime_type == "image/jpeg"
        second = pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        replacement = Picture(PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data)), PictureType.COVER_FRONT, "")

        with TestMp4.tagger.open(track1.filename) as file:
            file.remove_picture(first)
            file.add_picture(replacement, image_data)

        with TestMp4.tagger.open(track1.filename) as file:
            assert set(pic for (pic, _) in file.get_pictures()) == {replacement, second}
