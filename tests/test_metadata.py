import os

import pytest
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture

from albums.library.metadata import get_metadata, remove_embedded_image, set_basic_tags
from albums.types import Album, Picture, PictureType, Track

from .fixtures.create_library import create_library
from .fixtures.empty_files import IMAGE_PNG_400X400

albums = [
    Album("foo" + os.sep, [Track("1.mp3", {"tracknumber": ["1"], "tracktotal": ["3"], "discnumber": ["2"], "disctotal": ["2"]})]),
    Album(
        "bar" + os.sep,
        [
            Track("1.flac", {}, 0, 0, None, [Picture(PictureType.COVER_FRONT, "ignored", 0, 0, 0, b"")]),
            Track(
                "2.flac",
                {},
                0,
                0,
                None,
                [Picture(PictureType.COVER_FRONT, "ignored", 0, 0, 0, b""), Picture(PictureType.COVER_BACK, "ignored", 0, 0, 0, b"")],
            ),
        ],
    ),
    Album(
        "baz" + os.sep,
        [
            Track(
                "1.mp3",
                {"artist": ["A"], "albumartist": ["AA"], "title": ["T"], "album": ["baz"]},
                0,
                0,
                None,
                [Picture(PictureType.COVER_FRONT, "ignored", 0, 0, 0, b""), Picture(PictureType.COVER_BACK, "ignored", 0, 0, 0, b"")],
            )
        ],
    ),
    Album(
        "foobar" + os.sep,
        [
            Track(
                "1.ogg",
                {"tracknumber": ["1"], "tracktotal": ["1"], "artist": ["C"], "title": ["one"], "album": ["foobar"]},
                0,
                0,
                None,
                [Picture(PictureType.COVER_FRONT, "ignored", 0, 0, 0, b""), Picture(PictureType.COVER_BACK, "ignored", 0, 0, 0, b"")],
            )
        ],
    ),
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

    def test_read_flac_picture(self):
        file = TestMetadata.library / albums[1].path / albums[1].tracks[0].filename
        pictures = get_metadata(file)[2]
        assert len(pictures) == 1

        reference = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, len(IMAGE_PNG_400X400), b"")
        reference.file_hash = pictures[0].file_hash
        # all other fields are the same:
        assert pictures[0] == reference
        assert pictures[0].load_issue is None

    def test_read_flac_two_pictures(self):
        file = TestMetadata.library / albums[1].path / albums[1].tracks[1].filename
        pictures = get_metadata(file)[2]
        assert len(pictures) == 2

        reference = Picture(PictureType.COVER_FRONT, "image/png", 400, 400, len(IMAGE_PNG_400X400), b"")
        reference.file_hash = pictures[0].file_hash
        assert pictures[0] == reference
        assert pictures[0].embed_ix == 0
        reference.picture_type = PictureType.COVER_BACK
        assert pictures[1] == reference
        assert pictures[1].embed_ix == 1

    def test_read_flac_picture_mismatch(self):
        file = TestMetadata.library / albums[1].path / albums[1].tracks[0].filename
        mut = FLAC(file)
        mut.clear_pictures()
        pic = FlacPicture()
        pic.data = IMAGE_PNG_400X400
        pic.type = PictureType.COVER_FRONT
        pic.mime = "image/jpeg"  # wrong
        pic.width = 401  # wrong
        pic.height = 401  # wrong
        pic.depth = 8
        mut.add_picture(pic)
        mut.save()

        pictures = get_metadata(file)[2]
        assert len(pictures) == 1
        assert pictures[0].format == "image/png"
        assert pictures[0].width == 400
        assert pictures[0].height == 400
        assert pictures[0].load_issue == {"format": "image/jpeg", "width": 401, "height": 401}

    def test_read_write_id3_tags(self):
        track = albums[2].tracks[0]
        file = TestMetadata.library / albums[2].path / track.filename
        info = get_metadata(file)
        assert info
        (tags, _, pics) = info
        assert len(pics) == 2
        assert any(pic.description.endswith(" ") for pic in pics)  # ID3 frame hash was made unique by modifying description
        for pic in pics:
            pic.description = ""
        assert set(pics) == {
            Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T"),
            Picture(PictureType.COVER_BACK, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T"),
        }
        assert tags["artist"] == track.tags["artist"]
        assert tags["albumartist"] == track.tags["albumartist"]
        assert tags["album"] == track.tags["album"]
        assert tags["title"] == track.tags["title"]
        assert "TALB" not in tags
        assert "talb" not in tags

    def test_update_id3_tags(self):
        track = albums[2].tracks[0]
        file = TestMetadata.library / albums[2].path / track.filename
        assert set_basic_tags(file, [("artist", "a1"), ("albumartist", "a2"), ("album", "a3"), ("title", "t")])
        tags = get_metadata(file)[0]
        assert tags["artist"] == ["a1"]
        assert tags["albumartist"] == ["a2"]
        assert tags["album"] == ["a3"]
        assert tags["title"] == ["t"]
        assert "TALB" not in tags
        assert "talb" not in tags

    def test_read_oggvorbis(self):
        file = TestMetadata.library / albums[3].path / albums[3].tracks[0].filename
        info = get_metadata(file)
        assert info
        (tags, stream, pics) = info
        assert stream.codec == "Ogg Vorbis"
        assert pics == [
            Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T"),
            Picture(PictureType.COVER_BACK, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T"),
        ]
        assert tags["artist"] == ["C"]
        assert tags["title"] == ["one"]
        assert tags["album"] == ["foobar"]
        assert tags["tracknumber"] == ["1"]
        assert tags["tracktotal"] == ["1"]

    def test_remove_only_flac_pic(self):
        track = albums[1].tracks[0]
        file = TestMetadata.library / albums[1].path / track.filename
        info = get_metadata(file)
        assert info
        (_, stream, pics) = info
        assert stream.codec == "FLAC"
        assert pics == [Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T")]
        assert remove_embedded_image(file, stream.codec, pics[0])

        pics = get_metadata(file)[2]
        assert pics == []

    def test_remove_one_flac_pic(self):
        track = albums[1].tracks[1]
        file = TestMetadata.library / albums[1].path / track.filename
        info = get_metadata(file)
        assert info
        (_, stream, pics) = info
        assert stream.codec == "FLAC"
        pic1 = Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T")
        pic2 = Picture(PictureType.COVER_BACK, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T")
        assert pics == [pic1, pic2]
        assert remove_embedded_image(file, stream.codec, pic1)

        pics = get_metadata(file)[2]
        assert pics == [pic2]

    def test_remove_one_id3_pic(self):
        track = albums[2].tracks[0]
        file = TestMetadata.library / albums[2].path / track.filename
        info = get_metadata(file)
        assert info
        (_, stream, pics) = info
        assert stream.codec == "MP3"
        pic1 = Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T")
        pic2 = Picture(PictureType.COVER_BACK, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T", description=" ")
        assert set(pics) == {pic1, pic2}

        assert remove_embedded_image(file, stream.codec, pic1)

        pics = get_metadata(file)[2]
        assert pics == [pic2]

    def test_remove_one_ogg_vorbis_pic(self):
        track = albums[3].tracks[0]
        file = TestMetadata.library / albums[3].path / track.filename
        info = get_metadata(file)
        assert info
        (_, stream, pics) = info
        assert stream.codec == "Ogg Vorbis"
        assert len(pics) == 2
        pic1 = Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T")
        pic2 = Picture(PictureType.COVER_BACK, "image/png", width=400, height=400, file_size=543, file_hash=b"L\xc1#T")
        assert pics == [pic1, pic2]

        assert remove_embedded_image(file, stream.codec, pic1)

        pics = get_metadata(file)[2]
        assert pics == [pic2]
