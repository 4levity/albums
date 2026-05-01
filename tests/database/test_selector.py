import os
import re

import pytest
from sqlalchemy.orm import Session

from albums.database import connection
from albums.database.selector import Comparator, Match, load_album_entities
from albums.picture.info import PictureInfo
from albums.tagger.types import BasicTag, PictureType, StreamInfo
from albums.types import Album, PictureFile, Track, TrackPicture


class TestSelector:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestSelector.album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(
                    filename="1.flac",
                    tag={BasicTag.TITLE: "Foo", BasicTag.ARTIST: "Bar", BasicTag.ALBUMARTIST: "Various Artists", BasicTag.ALBUM: "=:="},
                    stream=StreamInfo(1.0, 128000, 2, "FLAC", 44100, 16),
                    pictures=[
                        TrackPicture(
                            picture_info=PictureInfo("image/jpeg", 200, 200, 24, 1024, b"1234", (("format", "image/png"),)),
                            picture_type=PictureType.COVER_FRONT,
                        )
                    ],
                )
            ],
            collections=["test"],
            ignore_checks=["artist-tag"],
            picture_files=[
                PictureFile(
                    filename="folder.jpg", picture_info=PictureInfo("test", 100, 100, 24, 4096, b"1234"), modify_timestamp=999, cover_source=True
                )
            ],
            scanner=3,
        )
        TestSelector.album2 = Album(
            path="baz" + os.sep,
            tracks=[
                Track(
                    filename="1.flac",
                    stream=StreamInfo(1.0, 64000, 2, "FLAC", 44100, 16),
                    tag={BasicTag.TITLE: "A", BasicTag.ARTIST: "Baz", BasicTag.ALBUM: "al bum"},
                ),
                Track(
                    filename="2.flac",
                    stream=StreamInfo(1.0, 128000, 2, "FLAC", 44100, 16),
                    tag={BasicTag.TITLE: "Foo", BasicTag.ARTIST: "Baz", BasicTag.ALBUM: "al bum"},
                ),
            ],
        )

    def test_select_empty(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                result = list(load_album_entities(session))
                assert len(result) == 0
        finally:
            db.dispose()

    def test_add_and_select(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.flush()
                assert len(list(load_album_entities(session))) == 1
                assert len(list(load_album_entities(session, {"path": [Match("foo")]}))) == 0  # no partial match
                result = list(load_album_entities(session, {"path": [Match("foo" + os.sep)]}))  # exact match
                assert len(result) == 1
                assert result[0].path == "foo" + os.sep
                assert result[0].scanner == 3
                assert sorted(result[0].tracks[0].get(BasicTag.ARTIST, default=[])) == ["Bar"]
                assert result[0].tracks[0].stream.length == 1.0
                assert result[0].tracks[0].stream.codec == "FLAC"
                assert len(result[0].tracks[0].pictures) == 1
                assert result[0].tracks[0].pictures[0].picture_type == PictureType.COVER_FRONT
                assert result[0].tracks[0].pictures[0].picture_info.file_size == 1024

                assert len(result[0].picture_files) == 1
                file = next(file for file in result[0].picture_files if file.filename == "folder.jpg")
                assert file.picture_info.mime_type == "test"
                assert file.picture_info.width == file.picture_info.height == 100
                assert file.picture_info.file_size == 4096
                assert file.picture_info.file_hash == b"1234"
                assert file.modify_timestamp == 999
                assert file.cover_source
        finally:
            db.dispose()

    def test_operators_strings(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                session.flush()
                assert len(list(load_album_entities(session))) == 2

                result = list(load_album_entities(session, {"path": [Match("f.o", Comparator.MATCH_REGEX)]}))
                assert len(result) == 1
                assert "foo" in result[0].path

                result = list(load_album_entities(session, {"path": [Match("foo" + os.sep, Comparator.NEQ)]}))
                assert len(result) == 1
                assert "baz" in result[0].path

                result = list(load_album_entities(session, {"path": [Match("baz" + os.sep, Comparator.GT)]}))
                assert len(result) == 1
                assert "foo" in result[0].path

                result = list(load_album_entities(session, {"path": [Match("baz" + os.sep, Comparator.GTE)]}))
                assert len(result) == 2

                result = list(load_album_entities(session, {"path": [Match("baz" + os.sep, Comparator.LT)]}))
                assert len(result) == 0

                result = list(load_album_entities(session, {"path": [Match("baz" + os.sep, Comparator.LTE)]}))
                assert len(result) == 1
                assert "baz" in result[0].path
        finally:
            db.dispose()

    def test_select_multiple_and_regex(self):
        db = connection.open(connection.MEMORY)
        try:
            re_sep = re.escape(os.sep)
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                assert len(list(load_album_entities(session))) == 2
                assert len(list(load_album_entities(session, {"path": [Match("o." + re_sep, Comparator.MATCH_REGEX)]}))) == 1  # regex match
                assert len(list(load_album_entities(session, {"path": [Match("x." + re_sep, Comparator.MATCH_REGEX)]}))) == 0  # no regex match
                assert len(list(load_album_entities(session, {"path": [Match("(foo|baz)", Comparator.MATCH_REGEX)]}))) == 2
        finally:
            db.dispose()

    def test_select_by_collection(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                result = list(load_album_entities(session, {"collection": [Match(".est", Comparator.MATCH_REGEX)]}))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
                result = list(load_album_entities(session, {"collection": [Match(".est")]}))
                assert len(result) == 0
                result = list(load_album_entities(session, {"collection": [Match("test"), Match("anything")]}))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
        finally:
            db.dispose()

    def test_select_by_collection_invert(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                result = list(load_album_entities(session, {"collection": [Match(".est", Comparator.MATCH_REGEX)]}, invert=True))
                assert len(result) == 1
                assert result[0].path.startswith("baz")
                result = list(load_album_entities(session, {"collection": [Match(".est")]}, invert=True))
                assert len(result) == 2
                result = list(load_album_entities(session, {"collection": [Match("test"), Match("anything")]}, invert=True))
                assert len(result) == 1
                assert result[0].path.startswith("baz")
        finally:
            db.dispose()

    def test_select_by_ignore_check(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                result = list(load_album_entities(session, {"ignore_check": [Match("artist-t", Comparator.MATCH_REGEX)]}))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
                result = list(load_album_entities(session, {"ignore_check": [Match("artist-t")]}))
                assert len(result) == 0
                result = list(load_album_entities(session, {"ignore_check": [Match("artist-tag")]}))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
        finally:
            db.dispose()

    def test_select_by_ignore_check_invert(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                result = list(load_album_entities(session, {"ignore_check": [Match("artist-t", Comparator.MATCH_REGEX)]}, invert=True))
                assert len(result) == 1
                assert result[0].path.startswith("baz")
                result = list(load_album_entities(session, {"ignore_check": [Match("artist-t")]}, invert=True))
                assert len(result) == 2
                result = list(load_album_entities(session, {"ignore_check": [Match("artist-tag")]}, invert=True))
                assert len(result) == 1
                assert result[0].path.startswith("baz")
        finally:
            db.dispose()

    def test_select_multiple_ignore_check(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                result = list(load_album_entities(session, {"ignore_check": [Match("artist-tag"), Match("anything")]}))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
                result = list(
                    load_album_entities(
                        session, {"ignore_check": [Match("artist-t", Comparator.MATCH_REGEX), Match("anything", Comparator.MATCH_REGEX)]}
                    )
                )
                assert len(result) == 1
                assert result[0].path.startswith("foo")

                result = list(load_album_entities(session, {"ignore_check": [Match("artist-tag"), Match("anything")]}, invert=True))
                assert len(result) == 1
                assert result[0].path.startswith("baz")
                result = list(
                    load_album_entities(
                        session, {"ignore_check": [Match("artist-t", Comparator.MATCH_REGEX), Match("anything", Comparator.MATCH_REGEX)]}, invert=True
                    )
                )
                assert len(result) == 1
                assert result[0].path.startswith("baz")

        finally:
            db.dispose()

    def test_select_by_tags(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                result = list(load_album_entities(session, {"tag:artist": [Match("Baz")]}))
                assert len(result) == 1
                assert result[0].path.startswith("baz")

                result = list(load_album_entities(session, {"tag:artist": [Match("Baz")]}, invert=True))
                assert len(result) == 1
                assert result[0].path.startswith("foo")

                result = list(load_album_entities(session, {"tag:title": [Match("F(o)o")]}))
                assert len(result) == 0

                result = list(load_album_entities(session, {"tag:title": [Match("F(o)o")]}, invert=True))
                assert len(result) == 2

                result = list(load_album_entities(session, {"tag:title": [Match("F(o)o", Comparator.MATCH_REGEX)]}))
                assert len(result) == 2

                result = list(load_album_entities(session, {"tag:title": [Match("F(o)o", Comparator.MATCH_REGEX)]}, invert=True))
                assert len(result) == 0

                result = list(load_album_entities(session, {"tag:title": [Match("Foo")]}))
                assert len(result) == 2

                result = list(load_album_entities(session, {"tag:title": [Match("Foo")], "tag:artist": [Match("Baz")]}))
                assert len(result) == 1
                assert result[0].path.startswith("baz")

                result = list(load_album_entities(session, {"tag:title": [Match("Foo")], "tag:artist": [Match("Baz")]}, invert=True))
                assert len(result) == 1
                assert result[0].path.startswith("foo")

                result = list(load_album_entities(session, {"tag:albumartist": []}))
                assert len(result) == 1
                assert result[0].path.startswith("foo")

                result = list(load_album_entities(session, {"tag:album": [Match("=:=")]}))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
        finally:
            db.dispose()

    def test_compare_any_track_bitrate(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                session.flush()

                result = list(load_album_entities(session, {"bitrate": [Match("64000")]}))
                assert len(result) == 1
                assert "baz" in result[0].path

                result = list(load_album_entities(session, {"bitrate": [Match("128000", Comparator.GTE)]}))
                assert len(result) == 2

                result = list(load_album_entities(session, {"bitrate": [Match("128000", Comparator.GT)]}))
                assert len(result) == 0

                result = list(load_album_entities(session, {"bitrate": [Match("64000")]}))
                assert len(result) == 1
                assert "baz" in result[0].path

                result = list(load_album_entities(session, {"bitrate": [Match("60000", Comparator.GT), Match("70000", Comparator.LT)]}))
                assert len(result) == 1
                assert "baz" in result[0].path

                result = list(load_album_entities(session, {"bitrate": [Match("128000", Comparator.LT)]}))
                assert len(result) == 1
                assert "baz" in result[0].path

                result = list(load_album_entities(session, {"bitrate": [Match("64000", Comparator.LTE)]}))
                assert len(result) == 1
                assert "baz" in result[0].path
        finally:
            db.dispose()
