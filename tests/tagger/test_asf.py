import os

import pytest

from albums.entities import Album, Track
from albums.tagger import AlbumTagger, BasicField, PictureType
from albums.tagger.file_types.asf import WmPicture

from ..fixtures.create_library import create_library

UUID0 = "00000000-0000-0000-0000-000000000000"
UUID1 = "11111111-1111-1111-1111-111111111111"
track = Track(
    filename="1.wma",
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
)
album = Album(path="baz" + os.sep, tracks=[track])


class TestAsf:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestAsf.library = create_library("tagger_asf", [album])
        TestAsf.tagger = AlbumTagger(TestAsf.library / album.path)

    def test_read_write_asf_tags(self):
        with TestAsf.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            fields = dict(file.get_fields())
        assert len(pictures) == 0  # not supported yet
        track_fields = track.field_dict()
        assert fields[BasicField.ARTIST] == tuple(track_fields[BasicField.ARTIST])
        assert fields[BasicField.ALBUMARTIST] == tuple(track_fields[BasicField.ALBUMARTIST])
        assert fields[BasicField.ALBUM] == tuple(track_fields[BasicField.ALBUM])
        assert fields[BasicField.TITLE] == tuple(track_fields[BasicField.TITLE])
        assert fields[BasicField.GENRE] == tuple(track_fields[BasicField.GENRE])
        assert fields[BasicField.MUSICBRAINZ_ALBUMID] == tuple(track_fields[BasicField.MUSICBRAINZ_ALBUMID])
        assert fields[BasicField.MUSICBRAINZ_TRACKID] == tuple(track_fields[BasicField.MUSICBRAINZ_TRACKID])
        assert fields[BasicField.ORGANIZATION] == tuple(track_fields[BasicField.ORGANIZATION])
        assert fields[BasicField.BARCODE] == tuple(track_fields[BasicField.BARCODE])
        assert fields[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == tuple(track_fields[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY])

    def test_update_asf_tags(self):
        TestAsf.tagger.set_basic_fields(
            TestAsf.library / album.path / track.filename,
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
        with TestAsf.tagger.open(track.filename) as file:
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

    def test_set_unsupported_asf_tags(self):
        with TestAsf.tagger.open(track.filename) as file:
            with pytest.raises(ValueError):
                file.set_field(BasicField.RELEASECOUNTRY, "UK")

    def test_remove_unsupported_asf_tags(self, mocker):
        with TestAsf.tagger.open(track.filename) as file:
            mock_logger = mocker.patch("albums.tagger.file_types.asf.logger")
            file.set_field(BasicField.RELEASECOUNTRY, None)
            assert mock_logger.warning.call_count == 1

    def test_update_asf_compilation(self):
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert BasicField.COMPILATION not in fields
            file.set_field(BasicField.COMPILATION, "1")  # normal enable
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert fields.get(BasicField.COMPILATION) == ("1",)

            file.set_field(BasicField.COMPILATION, None)  # normal disable
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert BasicField.COMPILATION not in fields

            file.set_field(BasicField.COMPILATION, "anything")
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert fields.get(BasicField.COMPILATION) == ("1",)  # set to anything = set to 1

    def test_write_asf_tracktotal(self):
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, "02")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("02",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "3")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("3",)
        assert fields[BasicField.TRACKTOTAL] == ("02",)

        # write both at once
        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "2")
            file.set_field(BasicField.TRACKTOTAL, "3")
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        # remove total
        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert BasicField.TRACKTOTAL not in fields

    def test_write_asf_disctotal(self):
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCTOTAL, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("1",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        # write both at once
        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "2")
            file.set_field(BasicField.DISCTOTAL, "2")
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        # remove total
        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert BasicField.DISCTOTAL not in fields

    def test_wm_picture_serialize(self):
        original = WmPicture(PictureType.FISH, "image/png", "Description", b"-image data-")
        serialized = original.to_bytes()
        from_bytes = WmPicture.from_bytes(serialized)
        assert original == from_bytes
