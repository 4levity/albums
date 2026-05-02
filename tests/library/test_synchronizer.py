import json
import os
import shutil
from string import Template
from unittest.mock import call

import pytest
from sqlalchemy.orm import Session

from albums.app import Context
from albums.config import ALL_ALBUMS, DEFAULT_FILE_CONVERT_PROFILE
from albums.database import connection
from albums.library.synchronizer import SyncDestination, Synchronizer
from albums.tagger.folder import AlbumTagger
from albums.types import Album, AlbumCollectionAssociation, BasicTag, CollectionEntity, StreamInfo, Track

from ..fixtures.create_library import create_library, test_data_path
from ..helpers import fake_ffmpeg


class TestSynchronizer:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestSynchronizer.transcoder_cache = test_data_path / "sync_transcoder_cache"
        TestSynchronizer.destination = test_data_path / "sync_dest"
        shutil.rmtree(TestSynchronizer.destination, ignore_errors=True)
        shutil.rmtree(TestSynchronizer.transcoder_cache, ignore_errors=True)
        os.makedirs(TestSynchronizer.destination)
        (TestSynchronizer.destination / "extra.txt").write_text("abc")

    def test_synchronizer(self, mocker):
        albums = [
            Album(
                path="foo" + os.sep,
                tracks=[
                    Track(filename="1.flac", tag={BasicTag.ARTIST: "baz", BasicTag.ALBUM: "foo", BasicTag.TITLE: "one"}),
                    Track(filename="2.flac", tag={BasicTag.ARTIST: "baz", BasicTag.ALBUM: "foo", BasicTag.TITLE: "two"}),
                ],
            ),
            Album(
                path="bar" + os.sep,
                tracks=[Track(filename="1.mp3", tag={BasicTag.ARTIST: "baz", BasicTag.ALBUM: "bar", BasicTag.TITLE: "aaa"})],
            ),
        ]
        mock_ensure_ffmpeg = mocker.patch("albums.library.transcoder.ensure_ffmpeg")
        mock_run_ffmpeg = mocker.patch("albums.library.transcoder.run_ffmpeg", side_effect=fake_ffmpeg)

        ctx = Context()
        ctx.config.transcoder_cache = TestSynchronizer.transcoder_cache
        ctx.config.library = create_library("sync", albums)
        ctx.db = connection.open(connection.MEMORY)
        try:
            with Session(ctx.db) as session:
                session.add_all(albums)
                test_collection = CollectionEntity(collection_name="test")
                session.add(test_collection)
                session.flush()
                session.add(AlbumCollectionAssociation(album=albums[0], collection=test_collection))
                session.add(AlbumCollectionAssociation(album=albums[1], collection=test_collection))
                session.commit()

            mp3_profile = "-b:a 192k mp3"
            dest = SyncDestination("test", TestSynchronizer.destination, Template(f"$artist{os.sep}$album"), Template(""), ["mp3"], mp3_profile)
            Synchronizer(ctx, dest).do_sync(True, True)

            assert mock_ensure_ffmpeg.call_count == 1
            foo_src_path = ctx.config.library / "foo"
            cache_index: dict[str, str] = json.loads((TestSynchronizer.transcoder_cache / "index.json").read_text())
            foo_cache_path = TestSynchronizer.transcoder_cache / cache_index[mp3_profile] / "foo"
            assert mock_run_ffmpeg.call_args_list == [
                call(["-i", "1.flac", "-b:a", "192k", str(foo_cache_path / "1.mp3")], foo_src_path),
                call(["-i", "2.flac", "-b:a", "192k", str(foo_cache_path / "2.mp3")], foo_src_path),
            ]
            foo_dest_path = TestSynchronizer.destination / "baz" / "foo"
            assert (foo_dest_path / "1.mp3").is_file()
            assert (foo_dest_path / "2.mp3").is_file()
            assert (TestSynchronizer.destination / "baz" / "bar" / "1.mp3").is_file()
            tagger = AlbumTagger(TestSynchronizer.destination / "baz" / "foo")
            with tagger.open("1.mp3") as file:
                t1 = dict(file.get_tags())
            with tagger.open("2.mp3") as file:
                t2 = dict(file.get_tags())
            assert t1.get(BasicTag.TITLE) == ("one",)
            assert t1.get(BasicTag.ALBUM) == ("foo",)
            assert t1.get(BasicTag.ARTIST) == ("baz",)
            assert t2.get(BasicTag.TITLE) == ("two",)
        finally:
            ctx.db.dispose()

    def test_synchronizer_choose_stream(self, mocker):
        albums = [
            Album(
                path="foo" + os.sep,
                tracks=[
                    Track(filename="1.flac", stream=StreamInfo(1, 900000, 2, "FLAC", 44100, 16), tag={BasicTag.ARTIST: "a", BasicTag.ALBUM: "foo"})
                ],
            ),
            Album(
                path="moo" + os.sep,
                tracks=[
                    Track(filename="1.flac", stream=StreamInfo(1, 800000, 2, "FLAC", 44100, 24), tag={BasicTag.ARTIST: "a", BasicTag.ALBUM: "foo"})
                ],
            ),
            Album(
                path="bar" + os.sep,
                tracks=[Track(filename="1.mp3", stream=StreamInfo(1, 160000, 2, "MP3", 48000), tag={BasicTag.ARTIST: "a", BasicTag.ALBUM: "bar"})],
            ),
            Album(
                path="baz" + os.sep,
                tracks=[Track(filename="1.mp3", stream=StreamInfo(1, 160000, 2, "MP3", 44100), tag={BasicTag.ARTIST: "a", BasicTag.ALBUM: "baz"})],
            ),
        ]
        mock_ensure_ffmpeg = mocker.patch("albums.library.transcoder.ensure_ffmpeg")
        mock_run_ffmpeg = mocker.patch("albums.library.transcoder.run_ffmpeg", side_effect=fake_ffmpeg)

        ctx = Context()
        ctx.config.transcoder_cache = TestSynchronizer.transcoder_cache
        ctx.config.library = create_library("sync2", albums)
        ctx.db = connection.open(connection.MEMORY)
        try:
            with Session(ctx.db) as session:
                session.add_all(albums)
                session.commit()

            dest = SyncDestination(
                ALL_ALBUMS,
                TestSynchronizer.destination,
                Template(f"$artist{os.sep}$album"),
                max_kbps=800,
                max_sample_rate=44100,
                max_bits_per_sample=16,
            )
            Synchronizer(ctx, dest).do_sync(True, True)

            assert mock_ensure_ffmpeg.call_count == 1
            cache_index: dict[str, str] = json.loads((TestSynchronizer.transcoder_cache / "index.json").read_text())
            cache_path = TestSynchronizer.transcoder_cache / cache_index[DEFAULT_FILE_CONVERT_PROFILE]
            assert mock_run_ffmpeg.call_args_list == [
                call(["-i", "1.mp3", str(cache_path / "bar" / "1.mp3")], ctx.config.library / "bar"),
                call(["-i", "1.flac", str(cache_path / "foo" / "1.mp3")], ctx.config.library / "foo"),
                call(["-i", "1.flac", str(cache_path / "moo" / "1.mp3")], ctx.config.library / "moo"),
            ]
        finally:
            ctx.db.dispose()
