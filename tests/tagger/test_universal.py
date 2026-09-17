import os

import pytest

from albums.entities import Album, Track
from albums.picture import PictureInfo
from albums.tagger import AlbumTagger, BasicField, Picture, PictureType
from albums.tagger.file_types.universal import UniversalTagger

from ..fixtures.create_library import create_library

album = Album(
    path="foo" + os.sep,
    tracks=[
        Track(filename="1.ogg", tag={BasicField.ARTIST: "C", BasicField.TITLE: "one", BasicField.ALBUM: "foobar"}),
        Track(filename="2.ogg", tag={BasicField.ORGANIZATION: "ABC", BasicField.DISCTOTAL: "2"}, legacy_fields=["label", "totaldiscs"]),
    ],
)
picture = Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, "")


def tagger(filename: str) -> UniversalTagger:
    return UniversalTagger(TestUniversal.library / album.path / filename, padding=lambda _: 0)


class TestUniversal:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestUniversal.library = create_library("tagger_universal", [album])

    def test_non_audio_file_raises(self, tmp_path):
        junk = tmp_path / "junk.xyz"
        junk.write_bytes(b"not audio")
        with pytest.raises(ValueError, match="can't open file"):
            UniversalTagger(junk, padding=lambda _: 0)

    def test_get_fields(self):
        fields = dict(tagger("1.ogg").get_fields())
        assert fields[BasicField.ARTIST] == ("C",)
        assert fields[BasicField.TITLE] == ("one",)
        assert fields[BasicField.ALBUM] == ("foobar",)

    def test_get_fields_returns_empty_on_error(self, mocker, caplog):
        caplog.set_level("WARNING")
        mocker.patch("albums.tagger.file_types.universal.vorbis_comment_fields", side_effect=Exception("boom"))
        assert tagger("1.ogg").get_fields() == ()
        assert any("error reading tags" in record.message for record in caplog.records)

    def test_get_legacy_fields(self):
        legacy = dict(tagger("2.ogg").get_legacy_fields())
        assert legacy == {"label": BasicField.ORGANIZATION, "totaldiscs": BasicField.DISCTOTAL}

    def test_get_legacy_fields_returns_empty_on_error(self, mocker, caplog):
        caplog.set_level("WARNING")
        mocker.patch("albums.tagger.file_types.universal.vorbis_comment_legacy_fields", side_effect=Exception("boom"))
        assert tagger("2.ogg").get_legacy_fields() == ()
        assert any("error reading legacy fields" in record.message for record in caplog.records)

    def test_get_pictures_yields_nothing(self):
        assert list(tagger("1.ogg").get_pictures()) == []

    def test_add_picture_not_supported(self):
        with pytest.raises(NotImplementedError, match="cannot add"):
            tagger("1.ogg").add_picture(picture, b"image")

    def test_remove_picture_not_supported(self):
        with pytest.raises(NotImplementedError, match="cannot remove"):
            tagger("1.ogg").remove_picture(picture)

    def test_get_image_data_raises(self):
        with pytest.raises(ValueError, match="cannot find matching"):
            tagger("1.ogg").get_image_data(picture)

    def test_set_field(self):
        file = tagger("1.ogg")
        file.set_field(BasicField.TITLE, ["two"])
        file.close()
        with AlbumTagger(TestUniversal.library / album.path).open("1.ogg") as tag:
            assert dict(tag.get_fields())[BasicField.TITLE] == ("two",)

    def test_set_field_logs_error(self, mocker, caplog):
        caplog.set_level("WARNING")
        mocker.patch("albums.tagger.file_types.universal.vorbis_comment_set_field", side_effect=Exception("boom"))
        tagger("1.ogg").set_field(BasicField.TITLE, ["two"])
        assert any("error setting" in record.message for record in caplog.records)
