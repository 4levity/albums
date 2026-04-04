import json
import os
import shutil
from unittest.mock import call

import pytest

from albums.app import Context
from albums.library.transcoder import Transcoder
from albums.types import Album, Track

from ..fixtures.create_library import test_data_path


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
