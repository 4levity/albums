import json
import os
import shutil
import time
from unittest.mock import call

import pytest

from albums.app import Context
from albums.library.transcoder import Transcoder
from albums.tagger.folder import AlbumTagger
from albums.types import Album, BasicTag, PictureInfo, PictureType, Track, TrackPicture

from ..fixtures.create_library import create_library, test_data_path
from ..helpers import fake_ffmpeg


class TestTranscoder:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        os.makedirs(test_data_path, exist_ok=True)
        TestTranscoder.transcoder_cache = test_data_path / "transcoder_cache"
        shutil.rmtree(TestTranscoder.transcoder_cache, ignore_errors=True)

    def test_transcoder(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1.flac"),
                Track(filename="2.flac"),
            ],
        )
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        mock_ensure_ffmpeg = mocker.patch("albums.library.transcoder.ensure_ffmpeg")
        mock_run_ffmpeg = mocker.patch("albums.library.transcoder.run_ffmpeg")
        profile = "-b:a 192k mp3"

        transcoder = Transcoder(ctx, profile)
        index_file = TestTranscoder.transcoder_cache / "index.json"

        assert not index_file.exists()  # deferred initialization
        assert not transcoder.in_cache(album, album.tracks[0])
        assert index_file.exists()  # initialized

        index: dict[str, str] = json.loads((index_file).read_text(encoding="utf-8"))
        dest_path = TestTranscoder.transcoder_cache / index[profile] / album.path
        mp3 = transcoder.get_transcoded(album, album.tracks[0])
        assert mp3 == dest_path / "1.mp3"
        mp3 = transcoder.get_transcoded(album, album.tracks[1])
        assert mp3 == dest_path / "2.mp3"

        assert mock_ensure_ffmpeg.call_count == 1
        source_path = ctx.config.library / album.path
        assert mock_run_ffmpeg.call_args_list == [
            call(["-i", "1.flac", "-b:a", "192k", str(dest_path / "1.mp3")], source_path),
            call(["-i", "2.flac", "-b:a", "192k", str(dest_path / "2.mp3")], source_path),
        ]

    def test_transcoder_uses_cache(self, mocker):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        mocker.patch("albums.library.transcoder.ensure_ffmpeg")
        mock_run_ffmpeg = mocker.patch("albums.library.transcoder.run_ffmpeg", side_effect=fake_ffmpeg)

        transcoder = Transcoder(ctx, "mp3")
        assert not transcoder.in_cache(album, album.tracks[0])
        transcoder.get_transcoded(album, album.tracks[0])
        assert mock_run_ffmpeg.call_count == 1
        transcoder.get_transcoded(album, album.tracks[0])
        assert mock_run_ffmpeg.call_count == 1

    def test_new_transcoder_uses_cache(self, mocker):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.library = create_library("test_reuse_transcoder_cache", [album])  # Transcoder uses library to validate cache, easiest to create it
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        mocker.patch("albums.library.transcoder.ensure_ffmpeg")
        mock_run_ffmpeg = mocker.patch("albums.library.transcoder.run_ffmpeg", side_effect=fake_ffmpeg)

        transcoder = Transcoder(ctx, "mp3")
        transcoder.get_transcoded(album, album.tracks[0])
        assert mock_run_ffmpeg.call_count == 1

        transcoder = Transcoder(ctx, "mp3")
        transcoder.get_transcoded(album, album.tracks[0])
        assert mock_run_ffmpeg.call_count == 1

    def test_transcoder_copies_tags(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(
                    filename="1.flac",
                    tag={BasicTag.TITLE: "one"},
                    pictures=[TrackPicture(picture_info=PictureInfo("image/jpeg", 400, 400, 24, 1024, b""), picture_type=PictureType.COVER_FRONT)],
                )
            ],
        )
        ctx = Context()
        ctx.config.library = create_library("test_transcoder_copy_tags", [album])
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        mocker.patch("albums.library.transcoder.ensure_ffmpeg")
        mocker.patch("albums.library.transcoder.run_ffmpeg", side_effect=fake_ffmpeg)

        transcoder = Transcoder(ctx, "mp3")
        mp3 = transcoder.get_transcoded(album, album.tracks[0])
        with AlbumTagger(mp3.parent).open(mp3.name) as tag:
            s = tag.scan()
            assert s.tags == ((BasicTag.TITLE, ("one",)),)
            assert len(s.pictures) == 1
            pic = s.pictures[0]
            assert pic.type == PictureType.COVER_FRONT
            assert pic.picture_info.mime_type == "image/jpeg"
            assert pic.picture_info.height == pic.picture_info.width == 400

    def test_transcoder_cache_cleanup(self, mocker):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac"), Track(filename="2.flac")])
        ctx = Context()
        ctx.config.library = create_library("test_transcoder_cache_cleanup", [album])
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        mocker.patch("albums.library.transcoder.ensure_ffmpeg")
        mocker.patch("albums.library.transcoder.run_ffmpeg", side_effect=fake_ffmpeg)

        transcoder = Transcoder(ctx, "mp3")
        transcoder.get_transcoded(album, album.tracks[0])
        transcoder.get_transcoded(album, album.tracks[1])

        (TestTranscoder.transcoder_cache / "1.txt").write_text("abc")
        (TestTranscoder.transcoder_cache / "a").mkdir()
        (TestTranscoder.transcoder_cache / "a" / "1.txt").write_text("abc")
        mp3_cache = TestTranscoder.transcoder_cache / str(json.loads((TestTranscoder.transcoder_cache / "index.json").read_text())["mp3"])
        (mp3_cache / "1.txt").write_text("abc")
        (mp3_cache / "a").mkdir()
        (mp3_cache / "a" / "1.txt").write_text("abc")
        (mp3_cache / "empty").mkdir()
        one_minute_ago = time.time() - 60
        os.utime(mp3_cache / "foo" / "2.mp3", (one_minute_ago, one_minute_ago))  # older than library
        (mp3_cache / "foo" / "3.mp3").write_text("abc")

        transcoder = Transcoder(ctx, "mp3")
        transcoder.get_transcoded(album, album.tracks[0])  # new transcoder, clean up cache on init
        assert not (TestTranscoder.transcoder_cache / "1.txt").exists()
        assert not (TestTranscoder.transcoder_cache / "a" / "1.txt").exists()
        assert not (TestTranscoder.transcoder_cache / "a").exists()
        assert not (mp3_cache / "1.txt").exists()
        assert not (mp3_cache / "a" / "1.txt").exists()
        assert not (mp3_cache / "a").exists()
        assert not (mp3_cache / "empty").exists()
        assert (mp3_cache / "foo" / "1.mp3").exists()
        assert not (mp3_cache / "foo" / "2.mp3").exists()
        assert not (mp3_cache / "foo" / "3.mp3").exists()

    def test_new_transcoder_deletes_older_cache(self, mocker):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.library = create_library("test_reuse_transcoder_cache", [album])  # Transcoder uses library to validate cache, easiest to create it
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        mocker.patch("albums.library.transcoder.ensure_ffmpeg")
        mocker.patch("albums.library.transcoder.run_ffmpeg", side_effect=fake_ffmpeg)

        transcoder = Transcoder(ctx, "mp3")
        old_mp3 = transcoder.get_transcoded(album, album.tracks[0])
        assert old_mp3.exists()
        index: dict[str, str] = json.loads((TestTranscoder.transcoder_cache / "index.json").read_text())
        assert "mp3" in index
        assert len(index) == 1

        transcoder = Transcoder(ctx, "-b:a 192k mp3")
        new_mp3 = transcoder.get_transcoded(album, album.tracks[0])
        assert new_mp3.exists()
        assert old_mp3.exists()  # cache is not full yet
        assert len(json.loads((TestTranscoder.transcoder_cache / "index.json").read_text())) == 2

        ctx.config.transcoder_cache_size = 1  # now, cache is over soft limit of 1 byte
        transcoder = Transcoder(ctx, "-b:a 192k mp3")
        new_mp3 = transcoder.get_transcoded(album, album.tracks[0])
        assert new_mp3.exists()  # cache is over limit but current profile cache is not deleted
        assert not old_mp3.exists()  # older cache is deleted
        index = json.loads((TestTranscoder.transcoder_cache / "index.json").read_text())
        assert len(index) == 1
        assert "mp3" not in index
        assert "-b:a 192k mp3" in index
