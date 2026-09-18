import json
import os
from pathlib import Path
from string import Template

import av
import pytest
from sqlalchemy.orm import Session

from albums.app import Context
from albums.config import ALL_ALBUMS, SyncDestination
from albums.database import MEMORY, db_open
from albums.entities import Album, AlbumCollectionAssociation, CollectionEntity, Track
from albums.library.synchronizer import Synchronizer
from albums.tagger import AlbumTagger, BasicField, StreamInfo

from ..fixtures.create_library import AudioSpec, create_library, create_track_file


class TestSynchronizer:
    @pytest.fixture(autouse=True)
    def setup_tests(self, tmp_path: Path):
        TestSynchronizer.transcoder_cache = tmp_path / "transcoder_cache"
        TestSynchronizer.destination = tmp_path / "dest"
        TestSynchronizer.destination.mkdir()
        (TestSynchronizer.destination / "extra.txt").write_text("abc")

    def test_synchronizer(self):
        albums = [
            Album(
                path="foo" + os.sep,
                tracks=[
                    Track(filename="1.flac", fields={BasicField.ARTIST: "baz", BasicField.ALBUM: "foo", BasicField.TITLE: "one"}),
                    Track(filename="2.flac", fields={BasicField.ARTIST: "baz", BasicField.ALBUM: "foo", BasicField.TITLE: "two"}),
                ],
            ),
            Album(
                path="bar" + os.sep,
                tracks=[Track(filename="1.mp3", fields={BasicField.ARTIST: "baz", BasicField.ALBUM: "bar", BasicField.TITLE: "aaa"})],
            ),
        ]
        ctx = Context()
        ctx.config.transcoder_cache = TestSynchronizer.transcoder_cache
        ctx.config.library = create_library("sync", albums, audio=AudioSpec())
        ctx.db = db_open(MEMORY)
        try:
            with Session(ctx.db) as session:
                session.add_all(albums)
                test_collection = CollectionEntity(collection_name="test")
                session.add(test_collection)
                session.flush()
                session.add(AlbumCollectionAssociation(album=albums[0], collection=test_collection))
                session.add(AlbumCollectionAssociation(album=albums[1], collection=test_collection))
                session.commit()

            dest = SyncDestination(
                "test", TestSynchronizer.destination, Template(f"$artist{os.sep}$album"), Template(""), ["mp3"], convert_bitrate="192"
            )
            Synchronizer(ctx, dest).do_sync(True, True)

            cache_index: dict[str, str] = json.loads((TestSynchronizer.transcoder_cache / "index.json").read_text())
            foo_cache_path = TestSynchronizer.transcoder_cache / cache_index["mp3:192"] / "foo"
            assert (foo_cache_path / "1.mp3").is_file()
            assert (foo_cache_path / "2.mp3").is_file()
            foo_dest_path = TestSynchronizer.destination / "baz" / "foo"
            assert (foo_dest_path / "1.mp3").is_file()
            assert (foo_dest_path / "2.mp3").is_file()
            assert (TestSynchronizer.destination / "baz" / "bar" / "1.mp3").is_file()
            with av.open(str(foo_dest_path / "1.mp3")) as container:
                assert container.streams.audio[0].codec_context.name in {"mp3", "mp3float"}
                assert container.streams.audio[0].codec_context.bit_rate == 192_000
            tagger = AlbumTagger(TestSynchronizer.destination / "baz" / "foo")
            with tagger.open("1.mp3") as file:
                t1 = dict(file.get_fields())
            with tagger.open("2.mp3") as file:
                t2 = dict(file.get_fields())
            assert t1[BasicField.TITLE] == ("one",)
            assert t1[BasicField.ALBUM] == ("foo",)
            assert t1[BasicField.ARTIST] == ("baz",)
            assert t2[BasicField.TITLE] == ("two",)
        finally:
            ctx.db.dispose()

    def test_synchronizer_choose_stream(self):
        albums = [
            Album(
                path="foo" + os.sep,
                tracks=[
                    Track(
                        filename="1.flac",
                        stream=StreamInfo(1, 900000, 2, "FLAC", 44100, 16),
                        fields={BasicField.ARTIST: "a", BasicField.ALBUM: "foo"},
                    )
                ],
            ),
            Album(
                path="moo" + os.sep,
                tracks=[
                    Track(
                        filename="1.flac",
                        stream=StreamInfo(1, 800000, 2, "FLAC", 44100, 24),
                        fields={BasicField.ARTIST: "a", BasicField.ALBUM: "foo"},
                    )
                ],
            ),
            Album(
                path="bar" + os.sep,
                tracks=[
                    Track(filename="1.mp3", stream=StreamInfo(1, 160000, 2, "MP3", 48000), fields={BasicField.ARTIST: "a", BasicField.ALBUM: "bar"})
                ],
            ),
            Album(
                path="baz" + os.sep,
                tracks=[
                    Track(filename="1.mp3", stream=StreamInfo(1, 160000, 2, "MP3", 44100), fields={BasicField.ARTIST: "a", BasicField.ALBUM: "baz"})
                ],
            ),
        ]
        ctx = Context()
        ctx.config.transcoder_cache = TestSynchronizer.transcoder_cache
        ctx.config.library = create_library("sync2", albums, audio=AudioSpec())
        create_track_file(
            ctx.config.library / "bar", albums[2].tracks[0], AudioSpec(sample_rate=48000)
        )  # 48kHz source, capped by max_sample_rate=44100
        ctx.db = db_open(MEMORY)
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

            # foo (over max_kbps), moo (over max_bits_per_sample) and bar (over max_sample_rate) are transcoded;
            # baz fits all caps and is copied as-is (foo and moo share an album tag, hence the same destination path)
            cache_index: dict[str, str] = json.loads((TestSynchronizer.transcoder_cache / "index.json").read_text())
            cache_path = TestSynchronizer.transcoder_cache / cache_index["mp3:vbr"]
            for album_path in ("bar", "foo", "moo"):
                assert (cache_path / album_path / "1.mp3").is_file()
            assert (TestSynchronizer.destination / "a" / "foo" / "1.mp3").is_file()
            assert (TestSynchronizer.destination / "a" / "bar" / "1.mp3").is_file()
            assert (TestSynchronizer.destination / "a" / "baz" / "1.mp3").is_file()
            with av.open(str(TestSynchronizer.destination / "a" / "bar" / "1.mp3")) as container:
                assert container.streams.audio[0].rate == 44100  # source 48kHz capped by max_sample_rate
        finally:
            ctx.db.dispose()
