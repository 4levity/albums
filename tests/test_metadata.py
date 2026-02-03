import pytest

from albums.library.metadata import get_metadata, set_basic_tags
from albums.types import Album, Track

from .fixtures.create_library import create_library

albums = [Album("foo/", [Track("1.mp3", {"tracknumber": ["1/3"], "discnumber": ["2/2"]})])]


class TestMetadata:
    @pytest.fixture(scope="module", autouse=True)
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

        # write both at once
        assert set_basic_tags(file, [("tracknumber", "2"), ("tracktotal", "3")])
        tags = get_metadata(file)[0]
        assert tags["tracknumber"] == ["2"]
        assert tags["tracktotal"] == ["3"]

    def test_write_id3_disctotal(self):
        file = TestMetadata.library / albums[0].path / albums[0].tracks[0].filename
        tags = get_metadata(file)[0]
        assert tags["discnumber"] == ["2"]
        assert tags["disctotal"] == ["2"]

        assert set_basic_tags(file, [("disctotal", "1")])
        tags = get_metadata(file)[0]
        assert tags["discnumber"] == ["2"]
        assert tags["disctotal"] == ["1"]

        # write both at once
        assert set_basic_tags(file, [("discnumber", "1"), ("disctotal", "2")])
        tags = get_metadata(file)[0]
        assert tags["discnumber"] == ["1"]
        assert tags["disctotal"] == ["2"]
