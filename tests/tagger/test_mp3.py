import os

import pytest
import xxhash

from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import AlbumPicture, PictureInfo
from albums.types import Album, Picture, PictureType, Track

from ..fixtures.create_library import create_library, make_image_data

track = Track(
    "1.mp3",
    {
        "artist": ["A"],
        "title": ["T"],
        "album": ["baz"],
        "albumartist": ["baz+foo"],
        "tracknumber": ["1"],
        "tracktotal": ["3"],
        "discnumber": ["2"],
        "disctotal": ["2"],
    },
    0,
    0,
    None,
    [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
)
album = Album("baz" + os.sep, [track])


class TestMp3:
    @pytest.fixture(scope="function", autouse=True)
    def setup_cli_tests(self):
        TestMp3.library = create_library("tagger_mp3", [album])
        TestMp3.tagger = AlbumTagger(TestMp3.library / album.path)

    def test_read_write_id3_tags(self):
        with TestMp3.tagger.open(track.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 2
        assert any(pic.description.endswith(" ") for pic in scan.pictures)  # ID3 frame hash was made unique by modifying description
        assert scan.pictures[0].picture_type == PictureType.COVER_FRONT or scan.pictures[1].picture_type == PictureType.COVER_FRONT
        assert scan.pictures[0].picture_type == PictureType.COVER_BACK or scan.pictures[1].picture_type == PictureType.COVER_BACK
        assert (
            scan.pictures[0].file_info.width
            == scan.pictures[0].file_info.height
            == scan.pictures[1].file_info.width
            == scan.pictures[1].file_info.height
            == 400
        )
        assert scan.pictures[0].file_info.mime_type == scan.pictures[1].file_info.mime_type == "image/png"
        tags = dict(scan.tags)
        assert tags[BasicTag.ARTIST] == tuple(track.tags["artist"])
        assert tags[BasicTag.ALBUMARTIST] == tuple(track.tags["albumartist"])
        assert tags[BasicTag.ALBUM] == tuple(track.tags["album"])
        assert tags[BasicTag.TITLE] == tuple(track.tags["title"])

    def test_update_id3_tags(self):
        TestMp3.tagger.set_basic_tags(
            TestMp3.library / album.path / track.filename, [("artist", "a1"), ("albumartist", "a2"), ("album", "a3"), ("title", "t")]
        )
        with TestMp3.tagger.open(track.filename) as file:
            scan = file.scan()
        tags = dict(scan.tags)
        assert tags[BasicTag.ARTIST] == ("a1",)
        assert tags[BasicTag.ALBUMARTIST] == ("a2",)
        assert tags[BasicTag.ALBUM] == ("a3",)
        assert tags[BasicTag.TITLE] == ("t",)

    def test_write_id3_tracktotal(self):
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, "02")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "3")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("3",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        # write both at once
        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "2")
            file.set_tag(BasicTag.TRACKTOTAL, "3")
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        # remove total
        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, None)
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert BasicTag.TRACKTOTAL not in tags

    def test_write_id3_disctotal(self):
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, "1")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "1")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("1",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        # write both at once
        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "2")
            file.set_tag(BasicTag.DISCTOTAL, "2")
        with TestMp3.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        # remove total
        with TestMp3.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, None)
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert BasicTag.DISCTOTAL not in tags

    def test_remove_one_id3_pic(self):
        with TestMp3.tagger.open(track.filename) as file:
            scan = file.scan()

        assert len(scan.pictures) == 2
        assert scan.pictures[0].picture_type == PictureType.COVER_FRONT
        assert scan.pictures[1].picture_type == PictureType.COVER_BACK
        assert (
            scan.pictures[0].file_info.width
            == scan.pictures[0].file_info.height
            == scan.pictures[1].file_info.width
            == scan.pictures[1].file_info.height
            == 400
        )
        assert scan.pictures[0].file_info.mime_type == scan.pictures[1].file_info.mime_type == "image/png"

        with TestMp3.tagger.open(track.filename) as file:
            file.remove_picture(scan.pictures[0])
        with TestMp3.tagger.open(track.filename) as file:
            scan = file.scan()

        assert len(scan.pictures) == 1
        assert scan.pictures[0].picture_type == PictureType.COVER_BACK
        assert scan.pictures[0].file_info.width == scan.pictures[0].file_info.height == 400
        assert scan.pictures[0].file_info.mime_type == "image/png"

    def test_replace_one_id3_pic(self):
        with TestMp3.tagger.open(track.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 2
        assert scan.pictures[0].picture_type == PictureType.COVER_FRONT
        front = scan.pictures[0]
        assert scan.pictures[1].picture_type == PictureType.COVER_BACK
        back = scan.pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        replacement = AlbumPicture(
            PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data)), PictureType.FISH, "", ()
        )

        with TestMp3.tagger.open(track.filename) as file:
            file.remove_picture(front)
            file.add_picture(replacement, image_data)

        with TestMp3.tagger.open(track.filename) as file:
            scan = file.scan()
        assert set(scan.pictures) == {replacement, back}
