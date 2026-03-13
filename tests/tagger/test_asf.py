import os

import pytest

from albums.tagger.asf import WmPicture
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import PictureType
from albums.types import Album, Tag, Track

from ..fixtures.create_library import create_library

track = Track(
    filename="1.wma",
    tags=[
        Tag(tag=BasicTag.ARTIST, value="A"),
        Tag(tag=BasicTag.TITLE, value="T"),
        Tag(tag=BasicTag.ALBUM, value="baz"),
        Tag(tag=BasicTag.ALBUMARTIST, value="baz+foo"),
        Tag(tag=BasicTag.TRACKNUMBER, value="1"),
        Tag(tag=BasicTag.TRACKTOTAL, value="3"),
        Tag(tag=BasicTag.DISCNUMBER, value="2"),
        Tag(tag=BasicTag.DISCTOTAL, value="2"),
    ],
)
album = Album(path="baz" + os.sep, tracks=[track])


class TestAsf:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestAsf.library = create_library("tagger_asf", [album])
        TestAsf.tagger = AlbumTagger(TestAsf.library / album.path)

    def test_read_write_asf_tags(self):
        with TestAsf.tagger.open(track.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 0  # not supported yet
        tags = dict(scan.tags)
        track_tags = track.tag_dict()
        assert tags[BasicTag.ARTIST] == tuple(track_tags[BasicTag.ARTIST])
        assert tags[BasicTag.ALBUMARTIST] == tuple(track_tags[BasicTag.ALBUMARTIST])
        assert tags[BasicTag.ALBUM] == tuple(track_tags[BasicTag.ALBUM])
        assert tags[BasicTag.TITLE] == tuple(track_tags[BasicTag.TITLE])

    def test_update_asf_tags(self):
        TestAsf.tagger.set_basic_tags(
            TestAsf.library / album.path / track.filename,
            [(BasicTag.ARTIST, "a1"), (BasicTag.ALBUMARTIST, "a2"), (BasicTag.ALBUM, "a3"), (BasicTag.TITLE, "t")],
        )
        with TestAsf.tagger.open(track.filename) as file:
            scan = file.scan()
        tags = dict(scan.tags)
        assert tags[BasicTag.ARTIST] == ("a1",)
        assert tags[BasicTag.ALBUMARTIST] == ("a2",)
        assert tags[BasicTag.ALBUM] == ("a3",)
        assert tags[BasicTag.TITLE] == ("t",)

    def test_write_asf_tracktotal(self):
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, "02")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "3")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("3",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        # write both at once
        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "2")
            file.set_tag(BasicTag.TRACKTOTAL, "3")
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        # remove total
        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, None)
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert BasicTag.TRACKTOTAL not in tags

    def test_write_asf_disctotal(self):
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, "1")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "1")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("1",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        # write both at once
        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "2")
            file.set_tag(BasicTag.DISCTOTAL, "2")
        with TestAsf.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        # remove total
        with TestAsf.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, None)
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert BasicTag.DISCTOTAL not in tags

    def test_wm_picture_serialize(self):
        original = WmPicture(PictureType.FISH, "image/png", "Description", b"-image data-")
        serialized = original.to_bytes()
        from_bytes = WmPicture.from_bytes(serialized)
        assert original == from_bytes
