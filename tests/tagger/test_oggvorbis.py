import os

import pytest
import xxhash

from albums.entities import Album, Track, TrackPicture
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicField
from albums.tagger.types import Picture, PictureType

from ..fixtures.create_library import create_library, make_image_data

UUID0 = "00000000-0000-0000-0000-000000000000"
UUID1 = "11111111-1111-1111-1111-111111111111"
track = Track(
    filename="1.ogg",
    tag={
        BasicField.ARTIST: "C",
        BasicField.TITLE: "one",
        BasicField.ALBUM: "foobar",
        BasicField.ALBUMARTIST: "foo",
        BasicField.TRACKNUMBER: "1",
        BasicField.TRACKTOTAL: "2",
        BasicField.DISCNUMBER: "3",
        BasicField.DISCTOTAL: "4",
        BasicField.GENRE: "Rock",
        BasicField.ORGANIZATION: "ABC",
        BasicField.BARCODE: "0123",
        BasicField.MUSICBRAINZ_ALBUMID: UUID0,
        BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY: "US",
    },
    pictures=[
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
        TrackPicture(picture_info=PictureInfo("image/jpeg", 300, 300, 24, 1, b""), picture_type=PictureType.COVER_BACK),
    ],
)
track_legacy = Track(
    filename="2.ogg",
    tag={BasicField.ORGANIZATION: "ABC", BasicField.ALBUMARTIST: "foo artist", BasicField.DISCTOTAL: "2"},
    legacy_tags=["label", "album artist", "totaldiscs"],
)
album = Album(path="foobar" + os.sep, tracks=[track, track_legacy])


class TestOggVorbis:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestOggVorbis.library = create_library("tagger_mp3", [album])
        TestOggVorbis.tagger = AlbumTagger(TestOggVorbis.library / album.path)

    def test_read_oggvorbis(self):
        with TestOggVorbis.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            tags = dict(file.get_tags())

        assert pictures[0].type == PictureType.COVER_FRONT
        assert pictures[0].picture_info.mime_type == "image/png"
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400

        assert pictures[1].type == PictureType.COVER_BACK
        assert pictures[1].picture_info.mime_type == "image/jpeg"
        assert pictures[1].picture_info.width == pictures[1].picture_info.height == 300

        track_tags = track.tag_dict()
        assert tags[BasicField.ARTIST] == tuple(track_tags[BasicField.ARTIST])
        assert tags[BasicField.TITLE] == tuple(track_tags[BasicField.TITLE])
        assert tags[BasicField.ALBUM] == tuple(track_tags[BasicField.ALBUM])
        assert tags[BasicField.ALBUMARTIST] == tuple(track_tags[BasicField.ALBUMARTIST])
        assert tags[BasicField.TRACKNUMBER] == tuple(track_tags[BasicField.TRACKNUMBER])
        assert tags[BasicField.TRACKTOTAL] == tuple(track_tags[BasicField.TRACKTOTAL])
        assert tags[BasicField.DISCNUMBER] == tuple(track_tags[BasicField.DISCNUMBER])
        assert tags[BasicField.DISCTOTAL] == tuple(track_tags[BasicField.DISCTOTAL])
        assert tags[BasicField.GENRE] == tuple(track_tags[BasicField.GENRE])
        assert tags[BasicField.ORGANIZATION] == tuple(track_tags[BasicField.ORGANIZATION])
        assert tags[BasicField.BARCODE] == tuple(track_tags[BasicField.BARCODE])
        assert tags[BasicField.MUSICBRAINZ_ALBUMID] == tuple(track_tags[BasicField.MUSICBRAINZ_ALBUMID])
        assert tags[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == tuple(track_tags[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY])

    def test_update_ogg_vorbis_tags(self):
        TestOggVorbis.tagger.set_basic_tags(
            TestOggVorbis.library / album.path / track.filename,
            [
                (BasicField.ARTIST, "a1"),
                (BasicField.TITLE, "t"),
                (BasicField.ALBUM, "a3"),
                (BasicField.ALBUMARTIST, "a2"),
                (BasicField.TRACKNUMBER, "5"),
                (BasicField.TRACKTOTAL, "6"),
                (BasicField.DISCNUMBER, "7"),
                (BasicField.DISCTOTAL, "8"),
                (BasicField.GENRE, "Country"),
                (BasicField.ORGANIZATION, "Q"),
                (BasicField.BARCODE, "0000"),
                (BasicField.MUSICBRAINZ_ALBUMID, UUID1),
                (BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY, "UK"),
            ],
        )
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicField.ARTIST] == ("a1",)
        assert tags[BasicField.TITLE] == ("t",)
        assert tags[BasicField.ALBUM] == ("a3",)
        assert tags[BasicField.ALBUMARTIST] == ("a2",)
        assert tags[BasicField.TRACKNUMBER] == ("5",)
        assert tags[BasicField.TRACKTOTAL] == ("6",)
        assert tags[BasicField.DISCNUMBER] == ("7",)
        assert tags[BasicField.DISCTOTAL] == ("8",)
        assert tags[BasicField.GENRE] == ("Country",)
        assert tags[BasicField.ORGANIZATION] == ("Q",)
        assert tags[BasicField.BARCODE] == ("0000",)
        assert tags[BasicField.MUSICBRAINZ_ALBUMID] == (UUID1,)
        assert tags[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == ("UK",)

    def test_update_ogg_vorbis_compilation(self):
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert BasicField.COMPILATION not in tags
            file.set_tag(BasicField.COMPILATION, "1")  # normal enable
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicField.COMPILATION) == ("1",)

            file.set_tag(BasicField.COMPILATION, None)  # normal disable
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert BasicField.COMPILATION not in tags

            file.set_tag(BasicField.COMPILATION, "anything")
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicField.COMPILATION) == ("1",)  # set to anything = set to 1

    def test_remove_one_ogg_vorbis_pic(self):
        with TestOggVorbis.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert len(pictures) == 2
        assert pictures[0].type == PictureType.COVER_FRONT
        assert pictures[0].picture_info.mime_type == "image/png"
        assert pictures[0].picture_info.width == pictures[0].picture_info.height == 400
        front = pictures[0]
        assert pictures[1].type == PictureType.COVER_BACK
        back = pictures[1]

        with TestOggVorbis.tagger.open(track.filename) as file:
            file.remove_picture(front)

        with TestOggVorbis.tagger.open(track.filename) as file:
            assert [pic for (pic, _) in file.get_pictures()] == [back]

    def test_replace_one_ogg_vorbis_pic(self):
        with TestOggVorbis.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

        assert len(pictures) == 2
        assert pictures[0].type == PictureType.COVER_FRONT
        front = pictures[0]
        assert pictures[1].type == PictureType.COVER_BACK
        back = pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        pic_info = PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data))
        replacement = Picture(pic_info, PictureType.FISH, "")

        with TestOggVorbis.tagger.open(track.filename) as file:
            file.remove_picture(front)
            file.add_picture(replacement, image_data)

        with TestOggVorbis.tagger.open(track.filename) as file:
            assert set(pic for (pic, _) in file.get_pictures()) == {replacement, back}

    def test_get_legacy_tags_present(self):
        with TestOggVorbis.tagger.open(track_legacy.filename) as file:
            legacy = file.get_legacy_tags()

        expected = (
            ("album artist", BasicField.ALBUMARTIST),
            ("label", BasicField.ORGANIZATION),
            ("totaldiscs", BasicField.DISCTOTAL),
        )
        assert sorted(legacy) == sorted(expected)

    def test_get_tags_legacy_mapping(self):
        with TestOggVorbis.tagger.open(track_legacy.filename) as file:
            tags = dict(file.get_tags())

        assert tags[BasicField.ORGANIZATION] == ("ABC",)
        assert tags[BasicField.ALBUMARTIST] == ("foo artist",)
        assert tags[BasicField.DISCTOTAL] == ("2",)
