import os
import re

import pytest
from sqlalchemy.orm import Session

from albums.database import connection, selector
from albums.database.models import AlbumEntity, PictureFileEntity, TrackEntity, TrackPictureEntity, TrackTagEntity
from albums.picture.info import PictureInfo
from albums.tagger.types import PictureType, StreamInfo
from albums.types import BasicTag


class TestSelector:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestSelector.album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.TITLE, value="Foo"),
                        TrackTagEntity(tag=BasicTag.ARTIST, value="Bar"),
                        TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Various Artists"),
                        TrackTagEntity(tag=BasicTag.ALBUM, value="=:="),
                    ],
                    stream=StreamInfo(1.0, 128000, 2, "FLAC", 44100),
                    pictures=[
                        TrackPictureEntity(
                            picture_info=PictureInfo("image/jpeg", 200, 200, 24, 1024, b"1234", (("format", "image/png"),)),
                            picture_type=PictureType.COVER_FRONT,
                        )
                    ],
                )
            ],
            collections=["test"],
            ignore_checks=["artist-tag"],
            picture_files=[
                PictureFileEntity(
                    filename="folder.jpg", picture_info=PictureInfo("test", 100, 100, 24, 4096, b"1234"), modify_timestamp=999, cover_source=True
                )
            ],
            scanner=3,
        )
        TestSelector.album2 = AlbumEntity(
            path="baz" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.TITLE, value="A"),
                        TrackTagEntity(tag=BasicTag.ARTIST, value="Baz"),
                        TrackTagEntity(tag=BasicTag.ALBUM, value="al bum"),
                    ],
                ),
                TrackEntity(
                    filename="2.flac",
                    tags=[
                        TrackTagEntity(tag=BasicTag.TITLE, value="Foo"),
                        TrackTagEntity(tag=BasicTag.ARTIST, value="Baz"),
                        TrackTagEntity(tag=BasicTag.ALBUM, value="al bum"),
                    ],
                ),
            ],
        )

    def test_select_empty(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                result = list(selector.load_album_entities(session))
                assert len(result) == 0
        finally:
            db.dispose()

    def test_add_and_select(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.flush()
                assert len(list(selector.load_album_entities(session))) == 1
                assert len(list(selector.load_album_entities(session, path=["foo"]))) == 0  # no partial match
                result = list(selector.load_album_entities(session, path=["foo" + os.sep]))  # exact match
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

    def test_select_multiple_and_regex(self):
        db = connection.open(connection.MEMORY)
        try:
            re_sep = re.escape(os.sep)
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                assert len(list(selector.load_album_entities(session))) == 2
                assert len(list(selector.load_album_entities(session, path=["o." + re_sep], regex=True))) == 1  # regex match
                assert len(list(selector.load_album_entities(session, path=["x." + re_sep], regex=True))) == 0  # no regex match
                assert len(list(selector.load_album_entities(session, path=["(foo|baz)"], regex=True))) == 2
        finally:
            db.dispose()

    def test_select_by_collection(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                TestSelector.album2.path = "baz" + os.sep
                TestSelector.album2.collections = []
                session.add(TestSelector.album2)
                result = list(selector.load_album_entities(session, collection=[".est"], regex=True))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
                result = list(selector.load_album_entities(session, collection=[".est"]))
                assert len(result) == 0
                result = list(selector.load_album_entities(session, collection=["test", "anything"]))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
        finally:
            db.dispose()

    def test_select_by_ignore_check(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                result = list(selector.load_album_entities(session, ignore_check=["artist-t"], regex=True))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
                result = list(selector.load_album_entities(session, ignore_check=["artist-t"]))
                assert len(result) == 0
                result = list(selector.load_album_entities(session, ignore_check=["artist-tag"]))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
        finally:
            db.dispose()

    def test_select_by_tags(self):
        db = connection.open(connection.MEMORY)
        try:
            with Session(db) as session:
                session.add(TestSelector.album)
                session.add(TestSelector.album2)
                result = list(selector.load_album_entities(session, tag=["artist:Baz"]))
                assert len(result) == 1
                assert result[0].path.startswith("baz")

                result = list(selector.load_album_entities(session, tag=["title:F(o)o"]))
                assert len(result) == 0

                result = list(selector.load_album_entities(session, tag=["title:F(o)o"], regex=True))
                assert len(result) == 2

                result = list(selector.load_album_entities(session, tag=["title:Foo"]))
                assert len(result) == 2

                result = list(selector.load_album_entities(session, tag=["title:Foo", "artist:Baz"]))
                assert len(result) == 1
                assert result[0].path.startswith("baz")

                result = list(selector.load_album_entities(session, tag=["albumartist"]))
                assert len(result) == 1
                assert result[0].path.startswith("foo")

                result = list(selector.load_album_entities(session, tag=["album:=:="]))
                assert len(result) == 1
                assert result[0].path.startswith("foo")
        finally:
            db.dispose()
