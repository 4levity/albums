import os

import pytest
import xxhash
from mutagen.id3._frames import TXXX
from mutagen.id3._specs import Encoding

from albums.entities import Album, Track, TrackPicture
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicField
from albums.tagger.types import Picture, PictureType

from ..fixtures.create_library import create_library, make_image_data

UUID0 = "00000000-0000-0000-0000-000000000000"
UUID1 = "11111111-1111-1111-1111-111111111111"
track = Track(
    filename="1.mp3",
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
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT, description=""),
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_BACK, description=""),
    ],
)
album = Album(path="baz" + os.sep, tracks=[track])


class TestMp3:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestMp3.library = create_library("tagger_mp3", [album])
        TestMp3.tagger = AlbumTagger(TestMp3.library / album.path)

    def test_read_write_id3_tag(self):
        with TestMp3.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            fields = dict(file.get_fields())
        assert len(pictures) == 2
        assert any(pic.description.endswith(" ") for pic in pictures)  # ID3 frame hash was made unique by modifying description
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
        assert fields[BasicField.ARTIST] == tuple(track_tags[BasicField.ARTIST])
        assert fields[BasicField.ALBUMARTIST] == tuple(track_tags[BasicField.ALBUMARTIST])
        assert fields[BasicField.ALBUM] == tuple(track_tags[BasicField.ALBUM])
        assert fields[BasicField.TITLE] == tuple(track_tags[BasicField.TITLE])
        assert fields[BasicField.GENRE] == tuple(track_tags[BasicField.GENRE])
        assert fields[BasicField.MUSICBRAINZ_ALBUMID] == tuple(track_tags[BasicField.MUSICBRAINZ_ALBUMID])
        assert fields[BasicField.MUSICBRAINZ_TRACKID] == tuple(track_tags[BasicField.MUSICBRAINZ_TRACKID])
        assert fields[BasicField.ORGANIZATION] == tuple(track_tags[BasicField.ORGANIZATION])
        assert fields[BasicField.BARCODE] == tuple(track_tags[BasicField.BARCODE])
        assert fields[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == tuple(track_tags[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY])

    def test_update_id3_tags(self):
        TestMp3.tagger.set_basic_fields(
            TestMp3.library / album.path / track.filename,
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
        with TestMp3.tagger.open(track.filename) as file:
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

    def test_set_unsupported_id3_tags(self):
        with TestMp3.tagger.open(track.filename) as file:
            with pytest.raises(ValueError):
                file.set_field(BasicField.RELEASETYPE, "EP")
            with pytest.raises(ValueError):
                file.set_field(BasicField.RELEASECOUNTRY, "UK")

    def test_remove_unsupported_id3_tags(self, mocker):
        with TestMp3.tagger.open(track.filename) as file:
            id3 = file._ensure_id3()
            id3["TXXX:RELEASECOUNTRY"] = TXXX(encoding=Encoding.UTF8, desc="RELEASECOUNTRY", text=["US"])

            fields = dict(file.get_fields())
            assert BasicField.RELEASECOUNTRY in fields

            mock_logger = mocker.patch("albums.tagger.base_id3.logger")
            # RELEASECOUNTRY uses TAG_TO_ID3_TEXT_FRAME mapping, so removal falls through to wildcard case (no warning)
            file.set_field(BasicField.RELEASECOUNTRY, None)
            assert mock_logger.warning.call_count == 0

            fields = dict(file.get_fields())
            assert BasicField.RELEASECOUNTRY not in fields

    def test_update_id3_compilation(self):
        with TestMp3.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert BasicField.COMPILATION not in fields
            file.set_field(BasicField.COMPILATION, "1")  # normal enable
        with TestMp3.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert fields.get(BasicField.COMPILATION) == ("1",)

            file.set_field(BasicField.COMPILATION, None)  # normal disable
        with TestMp3.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert BasicField.COMPILATION not in fields

            file.set_field(BasicField.COMPILATION, "anything")
        with TestMp3.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert fields.get(BasicField.COMPILATION) == ("1",)  # set to anything = set to 1

    def test_write_id3_tracktotal(self):
        with TestMp3.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, "02")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("02",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "3")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("3",)
        assert fields[BasicField.TRACKTOTAL] == ("02",)

        # write both at once
        with TestMp3.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "2")
            file.set_field(BasicField.TRACKTOTAL, "3")
        with TestMp3.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        # remove total
        with TestMp3.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert BasicField.TRACKTOTAL not in fields

    def test_write_id3_disctotal(self):
        with TestMp3.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCTOTAL, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("1",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        # write both at once
        with TestMp3.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "2")
            file.set_field(BasicField.DISCTOTAL, "2")
        with TestMp3.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        # remove total
        with TestMp3.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert BasicField.DISCTOTAL not in fields

    def test_remove_one_id3_pic(self):
        with TestMp3.tagger.open(track.filename) as file:
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

        with TestMp3.tagger.open(track.filename) as file:
            file.remove_picture(pictures[0])
        with TestMp3.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert len(pictures) == 1
        assert pictures[0].type == PictureType.COVER_BACK
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400
        assert pictures[0].picture_info.mime_type == "image/png"

    def test_replace_one_id3_pic(self):
        with TestMp3.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
        assert len(pictures) == 2
        assert pictures[0].type == PictureType.COVER_FRONT
        front = pictures[0]
        assert pictures[1].type == PictureType.COVER_BACK
        back = pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        replacement = Picture(PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data)), PictureType.FISH, "")

        with TestMp3.tagger.open(track.filename) as file:
            file.remove_picture(front)
            file.add_picture(replacement, image_data)

        with TestMp3.tagger.open(track.filename) as file:
            assert set(pic for (pic, _) in file.get_pictures()) == {replacement, back}
