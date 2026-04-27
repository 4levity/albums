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
    filename="1.ogg",
    tag={
        BasicTag.ARTIST: "C",
        BasicTag.TITLE: "one",
        BasicTag.ALBUM: "foobar",
        BasicTag.ALBUMARTIST: "foo",
        BasicTag.TRACKNUMBER: "1",
        BasicTag.TRACKTOTAL: "2",
        BasicTag.DISCNUMBER: "3",
        BasicTag.DISCTOTAL: "4",
        BasicTag.GENRE: "Rock",
        BasicTag.ORGANIZATION: "ABC",
        BasicTag.BARCODE: "0123",
        BasicTag.MUSICBRAINZ_ALBUMID: UUID0,
        BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY: "US",
    },
    pictures=[
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
        TrackPicture(picture_info=PictureInfo("image/jpeg", 300, 300, 24, 1, b""), picture_type=PictureType.COVER_BACK),
    ],
)
album = Album(path="foobar" + os.sep, tracks=[track])


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
        assert tags[BasicTag.ARTIST] == tuple(track_tags[BasicTag.ARTIST])
        assert tags[BasicTag.TITLE] == tuple(track_tags[BasicTag.TITLE])
        assert tags[BasicTag.ALBUM] == tuple(track_tags[BasicTag.ALBUM])
        assert tags[BasicTag.ALBUMARTIST] == tuple(track_tags[BasicTag.ALBUMARTIST])
        assert tags[BasicTag.TRACKNUMBER] == tuple(track_tags[BasicTag.TRACKNUMBER])
        assert tags[BasicTag.TRACKTOTAL] == tuple(track_tags[BasicTag.TRACKTOTAL])
        assert tags[BasicTag.DISCNUMBER] == tuple(track_tags[BasicTag.DISCNUMBER])
        assert tags[BasicTag.DISCTOTAL] == tuple(track_tags[BasicTag.DISCTOTAL])
        assert tags[BasicTag.GENRE] == tuple(track_tags[BasicTag.GENRE])
        assert tags[BasicTag.ORGANIZATION] == tuple(track_tags[BasicTag.ORGANIZATION])
        assert tags[BasicTag.BARCODE] == tuple(track_tags[BasicTag.BARCODE])
        assert tags[BasicTag.MUSICBRAINZ_ALBUMID] == tuple(track_tags[BasicTag.MUSICBRAINZ_ALBUMID])
        assert tags[BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == tuple(track_tags[BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY])

    def test_update_ogg_vorbis_tags(self):
        TestOggVorbis.tagger.set_basic_tags(
            TestOggVorbis.library / album.path / track.filename,
            [
                (BasicTag.ARTIST, "a1"),
                (BasicTag.TITLE, "t"),
                (BasicTag.ALBUM, "a3"),
                (BasicTag.ALBUMARTIST, "a2"),
                (BasicTag.TRACKNUMBER, "5"),
                (BasicTag.TRACKTOTAL, "6"),
                (BasicTag.DISCNUMBER, "7"),
                (BasicTag.DISCTOTAL, "8"),
                (BasicTag.GENRE, "Country"),
                (BasicTag.ORGANIZATION, "Q"),
                (BasicTag.BARCODE, "0000"),
                (BasicTag.MUSICBRAINZ_ALBUMID, UUID1),
                (BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY, "UK"),
            ],
        )
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
        assert tags[BasicTag.ARTIST] == ("a1",)
        assert tags[BasicTag.TITLE] == ("t",)
        assert tags[BasicTag.ALBUM] == ("a3",)
        assert tags[BasicTag.ALBUMARTIST] == ("a2",)
        assert tags[BasicTag.TRACKNUMBER] == ("5",)
        assert tags[BasicTag.TRACKTOTAL] == ("6",)
        assert tags[BasicTag.DISCNUMBER] == ("7",)
        assert tags[BasicTag.DISCTOTAL] == ("8",)
        assert tags[BasicTag.GENRE] == ("Country",)
        assert tags[BasicTag.ORGANIZATION] == ("Q",)
        assert tags[BasicTag.BARCODE] == ("0000",)
        assert tags[BasicTag.MUSICBRAINZ_ALBUMID] == (UUID1,)
        assert tags[BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == ("UK",)

    def test_update_ogg_vorbis_compilation(self):
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert BasicTag.COMPILATION not in tags
            file.set_tag(BasicTag.COMPILATION, "1")  # normal enable
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicTag.COMPILATION) == ("1",)

            file.set_tag(BasicTag.COMPILATION, None)  # normal disable
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert BasicTag.COMPILATION not in tags

            file.set_tag(BasicTag.COMPILATION, "anything")
        with TestOggVorbis.tagger.open(track.filename) as file:
            tags = dict(file.get_tags())
            assert tags.get(BasicTag.COMPILATION) == ("1",)  # set to anything = set to 1

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
