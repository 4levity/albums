import os

import pytest

from albums.entities import Album, Track
from albums.tagger.file_types.asf import WmPicture
from albums.tagger.folder import AlbumTagger, BasicField
from albums.tagger.types import PictureType

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
            tags = dict(file.get_tags())
        assert len(pictures) == 0  # not supported yet
        track_tags = track.tag_dict()
        assert tags[BasicField.ARTIST] == tuple(track_tags[BasicField.ARTIST])
        assert tags[BasicField.ALBUMARTIST] == tuple(track_tags[BasicField.ALBUMARTIST])
        assert tags[BasicField.ALBUM] == tuple(track_tags[BasicField.ALBUM])
        assert tags[BasicField.TITLE] == tuple(track_tags[BasicField.TITLE])
        assert tags[BasicField.GENRE] == tuple(track_tags[BasicField.GENRE])
        assert tags[BasicField.MUSICBRAINZ_ALBUMID] == tuple(track_tags[BasicField.MUSICBRAINZ_ALBUMID])
        assert tags[BasicField.MUSICBRAINZ_TRACKID] == tuple(track_tags[BasicField.MUSICBRAINZ_TRACKID])
        assert tags[BasicField.ORGANIZATION] == tuple(track_tags[BasicField.ORGANIZATION])
        assert tags[BasicField.BARCODE] == tuple(track_tags[BasicField.BARCODE])
        assert tags[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == tuple(track_tags[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY])

    def test_update_asf_tags(self):
        TestAsf.tagger.set_basic_tags(
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
            tags = dict(file.get_tags())
        assert tags[BasicField.ARTIST] == ("a1",)
        assert tags[BasicField.ALBUMARTIST] == ("a2",)
        assert tags[BasicField.ALBUM] == ("a3",)
        assert tags[BasicField.TITLE] == ("t",)
        assert tags[BasicField.GENRE] == ("Country",)
        assert tags[BasicField.MUSICBRAINZ_ALBUMID] == (UUID1,)
        assert tags[BasicField.MUSICBRAINZ_TRACKID] == (UUID0,)
        assert tags[BasicField.ORGANIZATION] == ("Q",)
        assert tags[BasicField.BARCODE] == ("0000",)
        assert tags[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == ("UK",)

    def test_set_unsupported_asf_tags(self):
        with TestAsf.tagger.open(track.filename) as file:
            with pytest.raises(ValueError):
                file.set_tag(BasicField.RELEASECOUNTRY, "UK")

    def test_remove_unsupported_asf_tags(self, mocker):
        with TestAsf.tagger.open(track.filename) as file:
            mock_logger = mocker.patch("albums.tagger.file_types.asf.logger")
            file.set_tag(BasicField.RELEASECOUNTRY, None)
            assert mock_logger.warning.call_count == 1

    def test_update_asf_compilation(self):
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert BasicField.COMPILATION not in tags
            file.set_tag(BasicField.COMPILATION, "1")  # normal enable
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicField.COMPILATION) == ("1",)

            file.set_tag(BasicField.COMPILATION, None)  # normal disable
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert BasicField.COMPILATION not in tags

            file.set_tag(BasicField.COMPILATION, "anything")
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicField.COMPILATION) == ("1",)  # set to anything = set to 1

    def test_write_asf_tracktotal(self):
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicField.TRACKNUMBER] == ("1",)
        assert tags[BasicField.TRACKTOTAL] == ("3",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicField.TRACKTOTAL, "02")
            tags = dict(file.get_tags())
        assert tags[BasicField.TRACKNUMBER] == ("1",)
        assert tags[BasicField.TRACKTOTAL] == ("02",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicField.TRACKNUMBER, "3")
            tags = dict(file.get_tags())
        assert tags[BasicField.TRACKNUMBER] == ("3",)
        assert tags[BasicField.TRACKTOTAL] == ("02",)

        # write both at once
        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicField.TRACKNUMBER, "2")
            file.set_tag(BasicField.TRACKTOTAL, "3")
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicField.TRACKNUMBER] == ("2",)
        assert tags[BasicField.TRACKTOTAL] == ("3",)

        # remove total
        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicField.TRACKTOTAL, None)
            tags = dict(file.get_tags())
        assert tags[BasicField.TRACKNUMBER] == ("2",)
        assert BasicField.TRACKTOTAL not in tags

    def test_write_asf_disctotal(self):
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicField.DISCNUMBER] == ("2",)
        assert tags[BasicField.DISCTOTAL] == ("2",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicField.DISCTOTAL, "1")
            tags = dict(file.get_tags())
        assert tags[BasicField.DISCNUMBER] == ("2",)
        assert tags[BasicField.DISCTOTAL] == ("1",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicField.DISCNUMBER, "1")
            tags = dict(file.get_tags())
        assert tags[BasicField.DISCNUMBER] == ("1",)
        assert tags[BasicField.DISCTOTAL] == ("1",)

        # write both at once
        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicField.DISCNUMBER, "2")
            file.set_tag(BasicField.DISCTOTAL, "2")
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicField.DISCNUMBER] == ("2",)
        assert tags[BasicField.DISCTOTAL] == ("2",)

        # remove total
        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicField.DISCTOTAL, None)
            tags = dict(file.get_tags())
        assert tags[BasicField.DISCNUMBER] == ("2",)
        assert BasicField.DISCTOTAL not in tags

    def test_wm_picture_serialize(self):
        original = WmPicture(PictureType.FISH, "image/png", "Description", b"-image data-")
        serialized = original.to_bytes()
        from_bytes = WmPicture.from_bytes(serialized)
        assert original == from_bytes
