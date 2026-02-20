import io
import os

import pytest
import xxhash
from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from PIL import Image

from albums.library.metadata import get_metadata, remove_embedded_image, replace_embedded_image, set_basic_tags
from albums.types import Album, Picture, PictureType, Track

from .fixtures.create_library import create_library, make_image_data

albums = [
    Album("foo" + os.sep, [Track("1.mp3", {"tracknumber": ["1"], "tracktotal": ["3"], "discnumber": ["2"], "disctotal": ["2"]})]),
    Album(
        "bar" + os.sep,
        [
            Track("1.flac", {}, 0, 0, None, [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
            Track(
                "2.flac",
                {},
                0,
                0,
                None,
                [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
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
                [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
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
                [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b""), Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")],
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

        assert pictures[0].picture_type == PictureType.COVER_FRONT
        assert pictures[0].format == "image/png"
        assert pictures[0].width == pictures[0].height == 400
        assert pictures[0].load_issue is None

    def test_read_flac_two_pictures(self):
        file = TestMetadata.library / albums[1].path / albums[1].tracks[1].filename
        pictures = get_metadata(file)[2]
        assert len(pictures) == 2

        assert pictures[0].picture_type == PictureType.COVER_FRONT
        assert pictures[0].format == "image/png"
        assert pictures[0].width == pictures[0].height == 400
        assert pictures[0].embed_ix == 0

        assert pictures[1].picture_type == PictureType.COVER_BACK
        assert pictures[1].format == "image/png"
        assert pictures[1].width == pictures[1].height == 400
        assert pictures[1].embed_ix == 1

    def test_read_flac_picture_mismatch(self):
        file = TestMetadata.library / albums[1].path / albums[1].tracks[0].filename
        mut = FLAC(file)
        mut.clear_pictures()
        pic = FlacPicture()
        pic.data = make_image_data(400, 400, "PNG")
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
        assert pics[0].picture_type == PictureType.COVER_FRONT or pics[1].picture_type == PictureType.COVER_FRONT
        assert pics[0].picture_type == PictureType.COVER_BACK or pics[1].picture_type == PictureType.COVER_BACK
        assert pics[0].width == pics[0].height == pics[1].width == pics[1].height == 400
        assert pics[0].format == pics[1].format == "image/png"
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
        (tags, stream, pictures) = info
        assert stream.codec == "Ogg Vorbis"

        assert pictures[0].picture_type == PictureType.COVER_FRONT
        assert pictures[0].format == "image/png"
        assert pictures[0].width == pictures[0].height == 400
        assert pictures[0].embed_ix == 0

        assert pictures[1].picture_type == PictureType.COVER_BACK
        assert pictures[1].format == "image/png"
        assert pictures[1].width == pictures[1].height == 400
        assert pictures[1].embed_ix == 1

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
        (_, stream, pictures) = info
        assert stream.codec == "FLAC"
        assert pictures[0].picture_type == PictureType.COVER_FRONT
        assert pictures[0].format == "image/png"
        assert pictures[0].width == pictures[0].height == 400
        assert pictures[0].embed_ix == 0
        assert remove_embedded_image(file, stream.codec, pictures[0])

        pics = get_metadata(file)[2]
        assert pics == []

    def test_remove_one_flac_pic(self):
        track = albums[1].tracks[1]
        file = TestMetadata.library / albums[1].path / track.filename
        info = get_metadata(file)
        assert info
        (_, stream, pictures) = info
        assert stream.codec == "FLAC"

        pic0 = Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=0, file_hash=b"")
        pic1 = Picture(PictureType.COVER_BACK, "image/png", width=400, height=400, file_size=0, file_hash=b"")

        assert pictures[0].picture_type == pic0.picture_type
        assert pictures[0].format == pic0.format
        assert pictures[0].width == pictures[0].height == pic0.width == pic0.height
        assert pictures[0].embed_ix == 0

        assert pictures[1].picture_type == pic1.picture_type
        assert pictures[1].format == pic1.format
        assert pictures[1].width == pictures[1].height == pic1.width == pic1.height
        assert pictures[1].embed_ix == 1

        pic0.file_size = pictures[0].file_size
        pic0.file_hash = pictures[0].file_hash
        assert remove_embedded_image(file, stream.codec, pic0)

        pictures = get_metadata(file)[2]
        assert len(pictures) == 1
        assert pictures[0].picture_type == pic1.picture_type
        assert pictures[0].format == pic1.format
        assert pictures[0].width == pictures[0].height == pic1.width == pic1.height
        assert pictures[0].embed_ix == 0

    def test_replace_one_flac_pic(self):
        file = TestMetadata.library / albums[1].path / albums[1].tracks[1].filename
        info = get_metadata(file)
        assert info
        (_, stream, pictures) = info
        assert pictures[0].picture_type == PictureType.COVER_FRONT
        pic0 = Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=pictures[0].file_size, file_hash=pictures[0].file_hash)
        pic1 = Picture(PictureType.COVER_BACK, "image/png", width=400, height=400, file_size=pictures[1].file_size, file_hash=pictures[1].file_hash)

        replacement_image = Image.new("RGB", (600, 600), color="blue")
        buffer = io.BytesIO()
        replacement_image.save(buffer, "JPEG")
        data = buffer.getvalue()
        replacement = Picture(PictureType.FISH, "image/jpeg", width=600, height=600, file_size=len(data), file_hash=xxhash.xxh32_digest(data))

        assert replace_embedded_image(file, stream.codec, pic0, replacement, replacement_image, data)
        assert set(get_metadata(file)[2]) == {pic1, replacement}

    def test_remove_one_id3_pic(self):
        track = albums[2].tracks[0]
        file = TestMetadata.library / albums[2].path / track.filename
        info = get_metadata(file)
        assert info
        (_, stream, pics) = info
        assert stream.codec == "MP3"
        pic0 = Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=0, file_hash=b"")
        assert len(pics) == 2
        assert pics[0].picture_type == PictureType.COVER_FRONT
        assert pics[1].picture_type == PictureType.COVER_BACK
        assert pics[0].width == pics[0].height == pics[1].width == pics[1].height == 400
        assert pics[0].format == pics[1].format == "image/png"

        pic0.file_size = pics[0].file_size
        pic0.file_hash = pics[0].file_hash
        assert remove_embedded_image(file, stream.codec, pic0)

        pics = get_metadata(file)[2]
        assert len(pics) == 1
        assert pics[0].picture_type == PictureType.COVER_BACK
        assert pics[0].width == pics[0].height == 400
        assert pics[0].format == "image/png"

    def test_replace_one_id3_pic(self):
        track = albums[2].tracks[0]
        file = TestMetadata.library / albums[2].path / track.filename
        info = get_metadata(file)
        assert info
        (_, stream, pics) = info
        assert stream.codec == "MP3"
        assert len(pics) == 2
        assert pics[0].picture_type == PictureType.COVER_FRONT
        assert pics[1].picture_type == PictureType.COVER_BACK
        assert pics[0].width == pics[0].height == pics[1].width == pics[1].height == 400
        pic0 = Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=pics[0].file_size, file_hash=pics[0].file_hash)
        other_pic = pics[1]

        replacement_image = Image.new("RGB", (600, 600), color="blue")
        buffer = io.BytesIO()
        replacement_image.save(buffer, "JPEG")
        data = buffer.getvalue()
        replacement = Picture(PictureType.FISH, "image/jpeg", width=600, height=600, file_size=len(data), file_hash=xxhash.xxh32_digest(data))

        assert replace_embedded_image(file, stream.codec, pic0, replacement, replacement_image, data)
        pics = get_metadata(file)[2]
        assert set(pics) == {replacement, other_pic}

    def test_remove_one_ogg_vorbis_pic(self):
        track = albums[3].tracks[0]
        file = TestMetadata.library / albums[3].path / track.filename
        info = get_metadata(file)
        assert info
        (_, stream, pictures) = info
        assert stream.codec == "Ogg Vorbis"
        assert len(pictures) == 2
        pic0 = Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=0, file_hash=b"")
        pic1 = Picture(PictureType.COVER_BACK, "image/png", width=400, height=400, file_size=0, file_hash=b"")
        assert pictures[0].picture_type == pic0.picture_type
        assert pictures[0].format == pic0.format
        assert pictures[0].width == pictures[0].height == pic0.width == pic0.height
        assert pictures[0].embed_ix == 0

        assert pictures[1].picture_type == pic1.picture_type
        assert pictures[1].format == pic1.format
        assert pictures[1].width == pictures[1].height == pic1.width == pic1.height
        assert pictures[1].embed_ix == 1

        pic0.file_size = pictures[0].file_size
        pic0.file_hash = pictures[0].file_hash
        assert remove_embedded_image(file, stream.codec, pic0)

        pictures = get_metadata(file)[2]
        assert len(pictures) == 1
        assert pictures[0].picture_type == pic1.picture_type
        assert pictures[0].format == pic1.format
        assert pictures[0].width == pictures[0].height == pic1.width == pic1.height
        assert pictures[0].embed_ix == 0

    def test_replace_one_ogg_vorbis_pic(self):
        track = albums[3].tracks[0]
        file = TestMetadata.library / albums[3].path / track.filename
        info = get_metadata(file)
        assert info
        (_, stream, pictures) = info
        assert stream.codec == "Ogg Vorbis"
        assert len(pictures) == 2
        assert pictures[0].picture_type == PictureType.COVER_FRONT
        assert pictures[1].picture_type == PictureType.COVER_BACK
        pic0 = Picture(PictureType.COVER_FRONT, "image/png", width=400, height=400, file_size=pictures[0].file_size, file_hash=pictures[0].file_hash)
        pic1 = Picture(PictureType.COVER_BACK, "image/png", width=400, height=400, file_size=pictures[1].file_size, file_hash=pictures[1].file_hash)

        replacement_image = Image.new("RGB", (600, 600), color="blue")
        buffer = io.BytesIO()
        replacement_image.save(buffer, "JPEG")
        data = buffer.getvalue()
        replacement = Picture(PictureType.FISH, "image/jpeg", width=600, height=600, file_size=len(data), file_hash=xxhash.xxh32_digest(data))

        assert replace_embedded_image(file, stream.codec, pic0, replacement, replacement_image, data)

        assert set(get_metadata(file)[2]) == {replacement, pic1}
