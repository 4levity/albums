import os

import pytest
import xxhash

from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import Picture, PictureType
from albums.types import Album, Track, TrackPicture

from ..fixtures.create_library import create_library, make_image_data

UUID0 = "00000000-0000-0000-0000-000000000000"
UUID1 = "11111111-1111-1111-1111-111111111111"
track = Track(
    filename="1.mp3",
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

    def test_read_write_id3_tags(self):
        with TestMp3.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            tags = dict(file.get_tags())
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
        assert tags[BasicTag.ARTIST] == tuple(track_tags[BasicTag.ARTIST])
        assert tags[BasicTag.ALBUMARTIST] == tuple(track_tags[BasicTag.ALBUMARTIST])
        assert tags[BasicTag.ALBUM] == tuple(track_tags[BasicTag.ALBUM])
        assert tags[BasicTag.TITLE] == tuple(track_tags[BasicTag.TITLE])
        assert tags[BasicTag.GENRE] == tuple(track_tags[BasicTag.GENRE])
        assert tags[BasicTag.MUSICBRAINZ_ALBUMID] == tuple(track_tags[BasicTag.MUSICBRAINZ_ALBUMID])
        assert tags[BasicTag.MUSICBRAINZ_TRACKID] == tuple(track_tags[BasicTag.MUSICBRAINZ_TRACKID])
        assert tags[BasicTag.ORGANIZATION] == tuple(track_tags[BasicTag.ORGANIZATION])
        assert tags[BasicTag.BARCODE] == tuple(track_tags[BasicTag.BARCODE])
        assert tags[BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == tuple(track_tags[BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY])

    def test_update_id3_tags(self):
        TestMp3.tagger.set_basic_tags(
            TestMp3.library / album.path / track.filename,
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
        with TestMp3.tagger.open(track.filename) as file:
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

    def test_set_unsupported_id3_tags(self):
        with TestMp3.tagger.open(track.filename) as file:
            with pytest.raises(ValueError):
                file.set_tag(BasicTag.OLD_TOTAL_DISCS, "2")
            with pytest.raises(ValueError):
                file.set_tag(BasicTag.RELEASETYPE, "EP")
            with pytest.raises(ValueError):
                file.set_tag(BasicTag.RELEASECOUNTRY, "UK")

    def test_remove_unsupported_id3_tags(self, mocker):
        with TestMp3.tagger.open(track.filename) as file:
            mock_logger = mocker.patch("albums.tagger.base_id3.logger")
            file.set_tag(BasicTag.OLD_TOTAL_DISCS, None)
            assert mock_logger.warning.call_count == 1
            file.set_tag(BasicTag.OLD_ALBUM_ARTIST, None)
            assert mock_logger.warning.call_count == 2

    def test_update_id3_compilation(self):
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert BasicTag.COMPILATION not in tags
            file.set_tag(BasicTag.COMPILATION, "1")  # normal enable
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicTag.COMPILATION) == ("1",)

            file.set_tag(BasicTag.COMPILATION, None)  # normal disable
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert BasicTag.COMPILATION not in tags

            file.set_tag(BasicTag.COMPILATION, "anything")
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicTag.COMPILATION) == ("1",)  # set to anything = set to 1

    def test_write_id3_tracktotal(self):
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, "02")
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "3")
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("3",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        # write both at once
        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "2")
            file.set_tag(BasicTag.TRACKTOTAL, "3")
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        # remove total
        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, None)
            tags = dict(file.get_tags())
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert BasicTag.TRACKTOTAL not in tags

    def test_write_id3_disctotal(self):
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, "1")
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "1")
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("1",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        # write both at once
        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "2")
            file.set_tag(BasicTag.DISCTOTAL, "2")
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        # remove total
        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, None)
            tags = dict(file.get_tags())
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert BasicTag.DISCTOTAL not in tags

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
