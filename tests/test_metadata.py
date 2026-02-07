import pytest

from albums.library.metadata import get_metadata, set_basic_tags
from albums.types import Album, Picture, PictureType, Track

from .fixtures.create_library import create_library
from .fixtures.empty_files import IMAGE_PNG_400X400

albums = [
    Album("foo/", [Track("1.mp3", {"tracknumber": ["1"], "tracktotal": ["3"], "discnumber": ["2"], "disctotal": ["2"]})]),
    Album("bar/", [Track("1.flac", {}, 0, 0, None, [Picture(PictureType.COVER_FRONT, "ignored", 0, 0, 0)])]),
    Album("baz/", [Track("1.mp3", {"artist": ["A"], "albumartist": ["AA"], "title": ["T"], "album": ["baz"]})]),
]


class TestMetadata:
    @pytest.fixture(scope="function", autouse=True)
    def setup_cli_tests(self):
        TestMetadata.library = create_library("metadata", albums)

    def test_write_id3_tracktotal(self):
        file = TestMetadata.library / albums[0].path / albums[0].tracks[0].filename
        tags = get_metadata(file)[0]
        assert tags["tracknumber"] == ["1"]
        assert tags["tracktotal"] == ["3"]

        assert set_basic_tags(file, [("tracktotal", "2")])
        tags = get_metadata(file)[0]
        assert tags["tracknumber"] == ["1"]
        assert tags["tracktotal"] == ["2"]

        assert set_basic_tags(file, [("tracknumber", "3")])
        tags = get_metadata(file)[0]
        assert tags["tracknumber"] == ["3"]
        assert tags["tracktotal"] == ["2"]

        # write both at once
        assert set_basic_tags(file, [("tracknumber", "2"), ("tracktotal", "3")])
        tags = get_metadata(file)[0]
        assert tags["tracknumber"] == ["2"]
        assert tags["tracktotal"] == ["3"]

        # remove total
        assert set_basic_tags(file, [("tracktotal", None)])
        tags = get_metadata(file)[0]
        assert tags["tracknumber"] == ["2"]
        assert "tracktotal" not in tags

    def test_write_id3_disctotal(self):
        file = TestMetadata.library / albums[0].path / albums[0].tracks[0].filename
        tags = get_metadata(file)[0]
        assert tags["discnumber"] == ["2"]
        assert tags["disctotal"] == ["2"]

        assert set_basic_tags(file, [("disctotal", "1")])
        tags = get_metadata(file)[0]
        assert tags["discnumber"] == ["2"]
        assert tags["disctotal"] == ["1"]

        assert set_basic_tags(file, [("discnumber", "1")])
        tags = get_metadata(file)[0]
        assert tags["discnumber"] == ["1"]
        assert tags["disctotal"] == ["1"]

        # write both at once
        assert set_basic_tags(file, [("discnumber", "2"), ("disctotal", "2")])
        tags = get_metadata(file)[0]
        assert tags["discnumber"] == ["2"]
        assert tags["disctotal"] == ["2"]

        # remove total
        assert set_basic_tags(file, [("disctotal", None)])
        tags = get_metadata(file)[0]
        assert tags["discnumber"] == ["2"]
        assert "disctotal" not in tags

    def test_read_write_picture(self):
        file = TestMetadata.library / albums[1].path / albums[1].tracks[0].filename
        pictures = get_metadata(file)[2]
        assert len(pictures) == 1
        assert pictures[0] == Picture(PictureType.COVER_FRONT, "image/png", 400, 400, len(IMAGE_PNG_400X400))

    def test_read_write_id3_tags(self):
        track = albums[2].tracks[0]
        file = TestMetadata.library / albums[2].path / track.filename
        tags = get_metadata(file)[0]
        assert tags["artist"] == track.tags["artist"]
        assert tags["albumartist"] == track.tags["albumartist"]
        assert tags["album"] == track.tags["album"]
        assert tags["title"] == track.tags["title"]

    def test_update_id3_tags(self):
        track = albums[2].tracks[0]
        file = TestMetadata.library / albums[2].path / track.filename
        assert set_basic_tags(file, [("artist", "a1"), ("albumartist", "a2"), ("album", "a3"), ("title", "t")])
        tags = get_metadata(file)[0]
        assert tags["artist"] == ["a1"]
        assert tags["albumartist"] == ["a2"]
        assert tags["album"] == ["a3"]
        assert tags["title"] == ["t"]
