import os

import pytest
import xxhash

from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import Picture, PictureType
from albums.types import Album, OtherFile, Track, TrackPicture

from ..fixtures.create_library import create_library, make_image_data

UUID0 = "00000000-0000-0000-0000-000000000000"
UUID1 = "11111111-1111-1111-1111-111111111111"
track1 = Track(
    filename="1.m4a",
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
        BasicTag.MUSICBRAINZ_ALBUMID: UUID0,
        BasicTag.MUSICBRAINZ_TRACKID: UUID1,
        BasicTag.ORGANIZATION: "ABC",
        BasicTag.BARCODE: "0123",
        BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY: "US",
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
        BasicTag.ARTIST: "A",
        BasicTag.TITLE: "T",
        BasicTag.ALBUM: "baz",
        BasicTag.ALBUMARTIST: "baz+foo",
        BasicTag.TRACKNUMBER: "2",
        BasicTag.TRACKTOTAL: "3",
        BasicTag.DISCNUMBER: "2",
        BasicTag.DISCTOTAL: "2",
        BasicTag.GENRE: "Rock",
        BasicTag.MUSICBRAINZ_ALBUMID: UUID0,
        BasicTag.MUSICBRAINZ_TRACKID: UUID1,
        BasicTag.ORGANIZATION: "ABC",
        BasicTag.BARCODE: "0123",
        BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY: "US",
    },
)
video = OtherFile(filename="video.mp4")
album = Album(path="baz" + os.sep, tracks=[track1, track2], other_files=[video])


class TestMp4:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestMp4.library = create_library("tagger_mp3", [album])
        TestMp4.tagger = AlbumTagger(TestMp4.library / album.path)

    def test_read_write_m4a_tags(self):
        with TestMp4.tagger.open(track1.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            tags = dict(file.get_tags())
            assert not file.has_video()
        assert len(pictures) == 2
        assert pictures[0].type == PictureType.COVER_FRONT
        assert pictures[0].picture_info.mime_type == "image/png"
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400
        assert pictures[1].type == PictureType.COVER_FRONT  # always
        assert pictures[1].picture_info.mime_type == "image/jpeg"
        assert pictures[1].picture_info.width == pictures[1].picture_info.height == 401
        track_tags = track1.tag_dict()
        assert tags[BasicTag.ARTIST] == tuple(track_tags[BasicTag.ARTIST])
        assert tags[BasicTag.ALBUMARTIST] == tuple(track_tags[BasicTag.ALBUMARTIST])
        assert tags[BasicTag.ALBUM] == tuple(track_tags[BasicTag.ALBUM])
        assert tags[BasicTag.TITLE] == tuple(track_tags[BasicTag.TITLE])
        assert tags[BasicTag.GENRE] == tuple(track_tags[BasicTag.GENRE])
        assert tags[BasicTag.TRACKNUMBER] == tuple(track_tags[BasicTag.TRACKNUMBER])
        assert tags[BasicTag.MUSICBRAINZ_ALBUMID] == tuple(track_tags[BasicTag.MUSICBRAINZ_ALBUMID])
        assert tags[BasicTag.MUSICBRAINZ_TRACKID] == tuple(track_tags[BasicTag.MUSICBRAINZ_TRACKID])
        assert tags[BasicTag.ORGANIZATION] == tuple(track_tags[BasicTag.ORGANIZATION])
        assert tags[BasicTag.BARCODE] == tuple(track_tags[BasicTag.BARCODE])
        assert tags[BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == tuple(track_tags[BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY])

    def test_mp4_audio(self):
        with TestMp4.tagger.open(track2.filename) as file:
            tags = dict(file.get_tags())
            assert not file.has_video()
        track_tags = track2.tag_dict()
        assert tags[BasicTag.TRACKNUMBER] == tuple(track_tags[BasicTag.TRACKNUMBER])

    def test_mp4_video(self):
        with TestMp4.tagger.open(video.filename) as file:
            assert file.has_video()
            pictures = [pic for (pic, _) in file.get_pictures()]
            tags = dict(file.get_tags())
            assert len(pictures) == 0
            assert len(tags) == 0
            file.set_tag(BasicTag.TRACKNUMBER, "3")
            image_data = make_image_data(600, 600, "JPEG")
            pic = Picture(PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data)), PictureType.COVER_FRONT, "")
            file.add_picture(pic, image_data)

        with TestMp4.tagger.open(video.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            assert pictures == [pic]
            assert file.get_tags() == ((BasicTag.TRACKNUMBER, ("3",)),)

    def test_update_mp4_tags(self):
        TestMp4.tagger.set_basic_tags(
            TestMp4.library / album.path / track1.filename,
            [
                (BasicTag.ARTIST, "a1"),
                (BasicTag.ALBUMARTIST, "a2"),
                (BasicTag.ALBUM, "a3"),
                (BasicTag.TITLE, "t"),
                (BasicTag.GENRE, "Country"),
                (BasicTag.MUSICBRAINZ_ALBUMID, UUID1),
                (BasicTag.MUSICBRAINZ_TRACKID, UUID0),
                (BasicTag.ORGANIZATION, "Q"),
                (BasicTag.BARCODE, "0000"),
                (BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY, "UK"),
            ],
        )
        with TestMp4.tagger.open(track1.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.ARTIST] == ("a1",)
        assert tags[BasicTag.ALBUMARTIST] == ("a2",)
        assert tags[BasicTag.ALBUM] == ("a3",)
        assert tags[BasicTag.TITLE] == ("t",)
        assert tags[BasicTag.GENRE] == ("Country",)
        assert tags[BasicTag.MUSICBRAINZ_ALBUMID] == (UUID1,)
        assert tags[BasicTag.MUSICBRAINZ_TRACKID] == (UUID0,)
        assert tags[BasicTag.ORGANIZATION] == ("Q",)
        assert tags[BasicTag.BARCODE] == ("0000",)
        assert tags[BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == ("UK",)

    def test_update_mp4_compilation(self):
        with TestMp4.tagger.open(track1.filename) as file:
            tags = dict(file.get_tags())
            assert BasicTag.COMPILATION not in tags
            file.set_tag(BasicTag.COMPILATION, "1")  # normal enable
        with TestMp4.tagger.open(track1.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicTag.COMPILATION) == ("1",)

            file.set_tag(BasicTag.COMPILATION, None)  # normal disable
        with TestMp4.tagger.open(track1.filename) as file:
            tags = dict(file.get_tags())
            assert BasicTag.COMPILATION not in tags

            file.set_tag(BasicTag.COMPILATION, "anything")
        with TestMp4.tagger.open(track1.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicTag.COMPILATION) == ("1",)  # set to anything = set to 1

    def test_write_mp4_tracktotal(self):
        with TestMp4.tagger.open(track1.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        with TestMp4.tagger.open(track1.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, "02")
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("2",)  # tag cannot store leading 0

        with TestMp4.tagger.open(track1.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "3")
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("3",)
        assert tags[BasicTag.TRACKTOTAL] == ("2",)

        # write both at once
        with TestMp4.tagger.open(track1.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "2")
            file.set_tag(BasicTag.TRACKTOTAL, "3")
        with TestMp4.tagger.open(track1.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        # remove total
        with TestMp4.tagger.open(track1.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, None)
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert BasicTag.TRACKTOTAL not in tags

    def test_write_mp4_disctotal(self):
        with TestMp4.tagger.open(track1.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        with TestMp4.tagger.open(track1.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, "1")
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        with TestMp4.tagger.open(track1.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "1")
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("1",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        # write both at once
        with TestMp4.tagger.open(track1.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "2")
            file.set_tag(BasicTag.DISCTOTAL, "2")
        with TestMp4.tagger.open(track1.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        # remove total
        with TestMp4.tagger.open(track1.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, None)
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert BasicTag.DISCTOTAL not in tags

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
