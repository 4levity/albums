import json
import os
import time
from pathlib import Path

import av
import pytest

from albums.app import Context
from albums.config import SyncDestination
from albums.entities import Album, Track, TrackPicture
from albums.library.transcoder import Transcoder
from albums.picture import PictureInfo
from albums.tagger import AlbumTagger, BasicField, PictureType

from ..fixtures.create_library import AudioSpec, create_audio_file, create_library


def _dest(file_type: str, bitrate: str, **kwargs) -> SyncDestination:
    return SyncDestination("", Path("dest"), convert_file_type=file_type, convert_bitrate=bitrate, **kwargs)


class TestTranscoder:
    @pytest.fixture(autouse=True)
    def setup_tests(self, tmp_path: Path):
        TestTranscoder.transcoder_cache = tmp_path / "transcoder_cache"

    def test_transcoder(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(filename="1.flac"),
                Track(filename="2.flac"),
            ],
        )
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        ctx.config.library = create_library("test_transcoder", [album], audio=AudioSpec())
        transcoder = Transcoder(ctx, _dest("mp3", "192"))
        index_file = TestTranscoder.transcoder_cache / "index.json"

        assert not index_file.exists()  # deferred initialization
        assert not transcoder.in_cache(album, album.tracks[0])
        assert index_file.exists()  # initialized

        index: dict[str, str] = json.loads((index_file).read_text(encoding="utf-8"))
        dest_path = TestTranscoder.transcoder_cache / index["mp3:192"] / album.path
        for track in album.tracks:
            mp3 = transcoder.get_transcoded(album, track)
            assert mp3 == dest_path / f"{track.filename[:1]}.mp3"
            assert mp3.exists()

        with av.open(str(dest_path / "1.mp3")) as container:
            stream = container.streams.audio[0]
            assert stream.codec_context.name in {"mp3", "mp3float"}
            assert stream.rate == 44100
            assert stream.codec_context.bit_rate == 192_000

    def test_transcoder_vbr(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        ctx.config.library = create_library("test_transcoder_vbr", [album], audio=AudioSpec(seconds=5))

        vbr_mp3 = Transcoder(ctx, _dest("mp3", "vbr")).get_transcoded(album, album.tracks[0])
        cbr_mp3 = Transcoder(ctx, _dest("mp3", "192")).get_transcoded(album, album.tracks[0])
        with av.open(str(vbr_mp3)) as container:
            assert container.streams.audio[0].codec_context.name in {"mp3", "mp3float"}
        # this simple tone encodes well under CBR 192k with VBR q2; if it were CBR it would match cbr_mp3's size
        assert vbr_mp3.stat().st_size < cbr_mp3.stat().st_size * 0.9

    def test_transcoder_m4a(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        ctx.config.library = create_library("test_transcoder_m4a", [album], audio=AudioSpec())

        transcoder = Transcoder(ctx, _dest("m4a", "192"))
        m4a = transcoder.get_transcoded(album, album.tracks[0])
        with av.open(str(m4a)) as container:
            stream = container.streams.audio[0]
            assert stream.codec_context.name == "aac"
            bit_rate = stream.codec_context.bit_rate
            assert bit_rate is not None
            assert 180_000 <= bit_rate <= 210_000

    def test_transcoder_flac(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        ctx.config.library = create_library("test_transcoder_flac", [album], audio=AudioSpec())

        transcoder = Transcoder(ctx, _dest("flac", ""))
        flac = transcoder.get_transcoded(album, album.tracks[0])
        with av.open(str(flac)) as container:
            stream = container.streams.audio[0]
            assert stream.codec_context.name == "flac"
            assert stream.rate == 44100

    def test_transcoder_resamples(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        ctx.config.library = create_library("test_transcoder_resample", [album], audio=AudioSpec(sample_rate=88200))

        transcoder = Transcoder(ctx, _dest("mp3", "192", max_sample_rate=44100))
        mp3 = transcoder.get_transcoded(album, album.tracks[0])
        with av.open(str(mp3)) as container:
            assert container.streams.audio[0].rate == 44100

    def test_transcoder_downmixes_to_stereo(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        ctx.config.library = create_library("test_transcoder_downmix", [album], audio=AudioSpec(channels=6))

        transcoder = Transcoder(ctx, _dest("mp3", "192"))
        mp3 = transcoder.get_transcoded(album, album.tracks[0])
        with av.open(str(mp3)) as container:
            assert container.streams.audio[0].layout.nb_channels == 2

    def test_transcoder_keeps_mono(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        ctx.config.library = create_library("test_transcoder_mono", [album], audio=AudioSpec(channels=1))

        transcoder = Transcoder(ctx, _dest("mp3", "192"))
        mp3 = transcoder.get_transcoded(album, album.tracks[0])
        with av.open(str(mp3)) as container:
            assert container.streams.audio[0].layout.nb_channels == 1

    def test_transcoder_24bit_source_becomes_16bit(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        ctx.config.library = create_library("test_transcoder_24bit", [album], audio=AudioSpec(bits=24))

        transcoder = Transcoder(ctx, _dest("flac", ""))
        flac = transcoder.get_transcoded(album, album.tracks[0])
        with av.open(str(flac)) as container:
            stream = container.streams.audio[0]
            first_frame = next(container.decode(stream))
            assert first_frame.format.name == "s16"  # 16-bit flac output is the desired behavior

    def test_transcoder_uses_cache(self, mocker):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache
        ctx.config.library = create_library("test_transcoder_uses_cache", [album], audio=AudioSpec())

        transcoder = Transcoder(ctx, _dest("mp3", "192"))
        assert not transcoder.in_cache(album, album.tracks[0])
        spy_transcode = mocker.spy(transcoder, "_transcode")
        transcoder.get_transcoded(album, album.tracks[0])
        transcoder.get_transcoded(album, album.tracks[0])
        assert spy_transcode.call_count == 1

    def test_new_transcoder_uses_cache(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.library = create_library("test_reuse_transcoder_cache", [album], audio=AudioSpec())  # Transcoder uses library to validate cache
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache

        transcoder = Transcoder(ctx, _dest("mp3", "vbr"))
        transcoder.get_transcoded(album, album.tracks[0])

        transcoder = Transcoder(ctx, _dest("mp3", "vbr"))
        transcoder.get_transcoded(album, album.tracks[0])  # cached, not re-transcoded

    def test_transcoder_copies_tags(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[
                Track(
                    filename="1.flac",
                    tag={BasicField.TITLE: "one"},
                    pictures=[TrackPicture(picture_info=PictureInfo("image/jpeg", 400, 400, 24, 1024, b""), picture_type=PictureType.COVER_FRONT)],
                )
            ],
        )
        ctx = Context()
        ctx.config.library = create_library("test_transcoder_copy_tags", [album], audio=AudioSpec())
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache

        transcoder = Transcoder(ctx, _dest("mp3", "192"))
        mp3 = transcoder.get_transcoded(album, album.tracks[0])
        with AlbumTagger(mp3.parent).open(mp3.name) as file:
            pictures = [pic for (pic, _) in file.get_pictures()]

            assert file.get_fields() == ((BasicField.TITLE, ("one",)),)
            assert len(pictures) == 1
            pic = pictures[0]
            assert pic.type == PictureType.COVER_FRONT
            assert pic.picture_info.mime_type == "image/jpeg"
            assert pic.picture_info.height == pic.picture_info.width == 400

    def test_transcoder_cache_cleanup(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac"), Track(filename="2.flac")])
        ctx = Context()
        ctx.config.library = create_library("test_transcoder_cache_cleanup", [album], audio=AudioSpec())
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache

        transcoder = Transcoder(ctx, _dest("mp3", "192"))
        transcoder.get_transcoded(album, album.tracks[0])
        transcoder.get_transcoded(album, album.tracks[1])

        (TestTranscoder.transcoder_cache / "1.txt").write_text("abc")
        (TestTranscoder.transcoder_cache / "a").mkdir()
        (TestTranscoder.transcoder_cache / "a" / "1.txt").write_text("abc")
        mp3_cache = TestTranscoder.transcoder_cache / str(json.loads((TestTranscoder.transcoder_cache / "index.json").read_text())["mp3:192"])
        (mp3_cache / "1.txt").write_text("abc")
        (mp3_cache / "a").mkdir()
        (mp3_cache / "a" / "1.txt").write_text("abc")
        (mp3_cache / "empty").mkdir()
        one_minute_ago = time.time() - 60
        os.utime(mp3_cache / "foo" / "2.mp3", (one_minute_ago, one_minute_ago))  # older than library
        create_audio_file(mp3_cache / "foo" / "3.mp3")

        transcoder = Transcoder(ctx, _dest("mp3", "192"))
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

    def test_new_transcoder_deletes_older_cache(self):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="1.flac")])
        ctx = Context()
        ctx.config.library = create_library(
            "test_new_transcoder_deletes_older_cache", [album], audio=AudioSpec()
        )  # Transcoder uses library to validate cache
        ctx.config.transcoder_cache = TestTranscoder.transcoder_cache

        transcoder = Transcoder(ctx, _dest("mp3", "vbr"))
        old_mp3 = transcoder.get_transcoded(album, album.tracks[0])
        assert old_mp3.exists()
        index: dict[str, str] = json.loads((TestTranscoder.transcoder_cache / "index.json").read_text())
        assert "mp3:vbr" in index
        assert len(index) == 1

        transcoder = Transcoder(ctx, _dest("mp3", "192"))
        new_mp3 = transcoder.get_transcoded(album, album.tracks[0])
        assert new_mp3.exists()
        assert old_mp3.exists()  # cache is not full yet
        assert len(json.loads((TestTranscoder.transcoder_cache / "index.json").read_text())) == 2

        ctx.config.transcoder_cache_size = 1  # now, cache is over soft limit of 1 byte
        transcoder = Transcoder(ctx, _dest("mp3", "192"))
        new_mp3 = transcoder.get_transcoded(album, album.tracks[0])
        assert new_mp3.exists()  # cache is over limit but current profile cache is not deleted
        assert not old_mp3.exists()  # older cache is deleted
        index = json.loads((TestTranscoder.transcoder_cache / "index.json").read_text())
        assert len(index) == 1
        assert "mp3:vbr" not in index
        assert "mp3:192" in index
