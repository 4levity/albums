# cspell:ignore Ünïcödé
import os
import shutil
import struct

import pytest
from mutagen.asf import ASF
from mutagen.asf._attrs import ASFBoolAttribute, ASFByteArrayAttribute

from albums.entities import Album, Track
from albums.picture import PictureScanner
from albums.tagger import AlbumTagger, BasicField, PictureType
from albums.tagger.file_types.asf import AsfTagger, WmPicture

from ..fixtures.create_library import create_library, make_image_data

UUID0 = "00000000-0000-0000-0000-000000000000"
UUID1 = "11111111-1111-1111-1111-111111111111"
track = Track(
    filename="1.wma",
    tag={
        BasicField.ARTIST: "A",
        BasicField.TITLE: "T",
        BasicField.ALBUM: "baz",
        BasicField.ALBUMARTIST: "baz+foo",
        BasicField.TRACKNUMBER: "1",
        BasicField.TRACKTOTAL: "3",
        BasicField.DISCNUMBER: "2",
        BasicField.DISCTOTAL: "2",
        BasicField.GENRE: "Rock",
        BasicField.MUSICBRAINZ_ALBUMID: UUID0,
        BasicField.MUSICBRAINZ_TRACKID: UUID1,
        BasicField.ORGANIZATION: "ABC",
        BasicField.BARCODE: "0123",
        BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY: "US",
        BasicField.DATE: "2020",
    },
)
album = Album(path="baz" + os.sep, tracks=[track])


class TestAsf:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestAsf.library = create_library("tagger_asf", [album])
        TestAsf.tagger = AlbumTagger(TestAsf.library / album.path)

    def test_read_write_asf_tags(self):
        with TestAsf.tagger.open(track.filename) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]
            fields = dict(file.get_fields())
        assert len(pictures) == 0  # not supported yet
        track_fields = track.field_dict()
        assert fields[BasicField.ARTIST] == tuple(track_fields[BasicField.ARTIST])
        assert fields[BasicField.ALBUMARTIST] == tuple(track_fields[BasicField.ALBUMARTIST])
        assert fields[BasicField.ALBUM] == tuple(track_fields[BasicField.ALBUM])
        assert fields[BasicField.TITLE] == tuple(track_fields[BasicField.TITLE])
        assert fields[BasicField.GENRE] == tuple(track_fields[BasicField.GENRE])
        assert fields[BasicField.MUSICBRAINZ_ALBUMID] == tuple(track_fields[BasicField.MUSICBRAINZ_ALBUMID])
        assert fields[BasicField.MUSICBRAINZ_TRACKID] == tuple(track_fields[BasicField.MUSICBRAINZ_TRACKID])
        assert fields[BasicField.ORGANIZATION] == tuple(track_fields[BasicField.ORGANIZATION])
        assert fields[BasicField.BARCODE] == tuple(track_fields[BasicField.BARCODE])
        assert fields[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == tuple(track_fields[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY])
        assert fields[BasicField.DATE] == tuple(track_fields[BasicField.DATE])

    def test_update_asf_tags(self):
        TestAsf.tagger.set_basic_fields(
            TestAsf.library / album.path / track.filename,
            [
                (BasicField.ARTIST, "a1"),
                (BasicField.ALBUMARTIST, "a2"),
                (BasicField.ALBUM, "a3"),
                (BasicField.TITLE, "t"),
                (BasicField.GENRE, "Country"),
                (BasicField.MUSICBRAINZ_ALBUMID, UUID1),
                (BasicField.MUSICBRAINZ_TRACKID, UUID0),
                (BasicField.ORGANIZATION, "Q"),
                (BasicField.BARCODE, "0000"),
                (BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY, "UK"),
                (BasicField.DATE, "2021"),
            ],
        )
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.ARTIST] == ("a1",)
        assert fields[BasicField.ALBUMARTIST] == ("a2",)
        assert fields[BasicField.ALBUM] == ("a3",)
        assert fields[BasicField.TITLE] == ("t",)
        assert fields[BasicField.GENRE] == ("Country",)
        assert fields[BasicField.MUSICBRAINZ_ALBUMID] == (UUID1,)
        assert fields[BasicField.MUSICBRAINZ_TRACKID] == (UUID0,)
        assert fields[BasicField.ORGANIZATION] == ("Q",)
        assert fields[BasicField.BARCODE] == ("0000",)
        assert fields[BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY] == ("UK",)
        assert fields[BasicField.DATE] == ("2021",)

    def test_remove_asf_release_date(self):
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DATE] == ("2020",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.DATE, None)
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert BasicField.DATE not in fields

    def test_set_unsupported_asf_tags(self):
        with TestAsf.tagger.open(track.filename) as file:
            with pytest.raises(ValueError):
                file.set_field(BasicField.RELEASECOUNTRY, "UK")

    def test_remove_unsupported_asf_tags(self, mocker):
        with TestAsf.tagger.open(track.filename) as file:
            mock_logger = mocker.patch("albums.tagger.file_types.asf.logger")
            file.set_field(BasicField.RELEASECOUNTRY, None)
            assert mock_logger.warning.call_count == 1

    def test_update_asf_compilation(self):
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert BasicField.COMPILATION not in fields
            file.set_field(BasicField.COMPILATION, "1")  # normal enable
        # MS-ASF defines WM/IsCompilation as a Boolean attribute, so a conformant bool must be written
        asf = ASF(str(TestAsf.library / album.path / track.filename))
        assert isinstance(asf.tags["WM/IsCompilation"][0], ASFBoolAttribute)
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert fields.get(BasicField.COMPILATION) == ("1",)

            file.set_field(BasicField.COMPILATION, None)  # normal disable
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert BasicField.COMPILATION not in fields

            file.set_field(BasicField.COMPILATION, "anything")
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
            assert fields.get(BasicField.COMPILATION) == ("1",)  # set to anything = set to 1

    def test_read_asf_compilation_boolean(self, tmp_path):
        # a WMA written by a conformant tool stores WM/IsCompilation as a Boolean attribute; it must be
        # read back as the standard "1" value (not "True") so it is not "fixed" into a non-conformant string
        wma = tmp_path / "1.wma"
        shutil.copy(TestAsf.library / album.path / track.filename, wma)
        asf = ASF(str(wma))
        asf.tags["WM/IsCompilation"] = [True]
        asf.save()

        tagger_file = AsfTagger(wma, picture_scanner=PictureScanner(), padding=lambda info: 0)
        try:
            fields = dict(tagger_file.get_fields())
            assert fields[BasicField.COMPILATION] == ("1",)
        finally:
            tagger_file.close()

        asf = ASF(str(wma))
        asf.tags["WM/IsCompilation"] = [False]
        asf.save()

        tagger_file = AsfTagger(wma, picture_scanner=PictureScanner(), padding=lambda info: 0)
        try:
            fields = dict(tagger_file.get_fields())
            assert BasicField.COMPILATION not in fields  # false boolean = flag not set
        finally:
            tagger_file.close()

    def test_write_asf_tracktotal(self):
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, "02")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("1",)
        assert fields[BasicField.TRACKTOTAL] == ("02",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "3")
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("3",)
        assert fields[BasicField.TRACKTOTAL] == ("02",)

        # write both at once
        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKNUMBER, "2")
            file.set_field(BasicField.TRACKTOTAL, "3")
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert fields[BasicField.TRACKTOTAL] == ("3",)

        # remove total
        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.TRACKTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.TRACKNUMBER] == ("2",)
        assert BasicField.TRACKTOTAL not in fields

    def test_write_asf_disctotal(self):
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCTOTAL, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "1")
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("1",)
        assert fields[BasicField.DISCTOTAL] == ("1",)

        # write both at once
        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCNUMBER, "2")
            file.set_field(BasicField.DISCTOTAL, "2")
        with TestAsf.tagger.open(track.filename) as file:
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert fields[BasicField.DISCTOTAL] == ("2",)

        # remove total
        with TestAsf.tagger.open(track.filename) as file:
            file.set_field(BasicField.DISCTOTAL, None)
            fields = dict(file.get_fields())
        assert fields[BasicField.DISCNUMBER] == ("2",)
        assert BasicField.DISCTOTAL not in fields

    @staticmethod
    def wm_picture_blob(picture_type: int, mime_type: str, description: str, image_data: bytes) -> bytes:
        # spec-compliant WM/Picture blob: type, image size, null-terminated UTF-16LE mime type and
        # description, then image data
        return (
            struct.pack("<bi", picture_type, len(image_data))
            + mime_type.encode("utf-16-le")
            + b"\x00\x00"
            + description.encode("utf-16-le")
            + b"\x00\x00"
            + image_data
        )

    def test_wm_picture_serialize(self):
        original = WmPicture(PictureType.FISH, "image/png", "Description", b"-image data-")
        serialized = original.to_bytes()
        from_bytes = WmPicture.from_bytes(serialized)
        assert original == from_bytes

    def test_wm_picture_serialize_edge_cases(self):
        # empty strings and non-ASCII text
        for original in (
            WmPicture(PictureType.OTHER, "", "", b"xyz"),
            WmPicture(PictureType.COVER_FRONT, "image/jpeg", "Ünïcödé 中文", b"img"),
        ):
            assert WmPicture.from_bytes(original.to_bytes()) == original

    def test_wm_picture_from_bytes_malformed(self):
        full = self.wm_picture_blob(3, "image/png", "desc", b"0123456789ABCDEF")
        for raw in (
            full[:12],  # MIME type without null terminator
            full[:30],  # description without null terminator
            full[:-13],  # image data shorter than declared size
            b"\x03",  # shorter than the 5-byte header
            b"",  # empty
        ):
            with pytest.raises(ValueError):
                WmPicture.from_bytes(raw)

    def test_wm_picture_from_bytes_trailing_data(self, mocker):
        mock_logger = mocker.patch("albums.tagger.file_types.asf.logger")
        raw = self.wm_picture_blob(3, "image/png", "desc", b"ABC") + b"TRAILING"
        from_bytes = WmPicture.from_bytes(raw)
        assert from_bytes.image_data == b"ABC"
        assert mock_logger.warning.call_count == 1

    def test_read_wm_picture_from_file(self, tmp_path):
        # embed spec-compliant WM/Picture blobs in a real WMA file and read them back through the full
        # read path (ASF container -> WmPicture -> picture scanner)
        wma = tmp_path / "pic.wma"
        shutil.copy(TestAsf.library / album.path / track.filename, wma)
        asf = ASF(str(wma))
        red = make_image_data(64, 64, "PNG", "red")
        green = make_image_data(32, 48, "PNG", "green")
        asf.tags["WM/Picture"] = [
            ASFByteArrayAttribute(self.wm_picture_blob(PictureType.COVER_FRONT.value, "image/png", "front cover", red)),
            ASFByteArrayAttribute(self.wm_picture_blob(PictureType.ILLUSTRATION.value, "image/png", "illustration", green)),
        ]
        asf.save()

        tagger_file = AsfTagger(wma, picture_scanner=PictureScanner(), padding=lambda info: 0)
        try:
            pictures = list(tagger_file.get_pictures())
        finally:
            tagger_file.close()

        assert [(pic.type, pic.description, pic.picture_info.mime_type, pic.picture_info.width, pic.picture_info.height) for pic, _ in pictures] == [
            (PictureType.COVER_FRONT, "front cover", "image/png", 64, 64),
            (PictureType.ILLUSTRATION, "illustration", "image/png", 32, 48),
        ]
        assert [data for _, data in pictures] == [red, green]
