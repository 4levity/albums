"""Transcode audio into a persistent, size-managed cache of transcoded files."""

from __future__ import annotations

import glob
import json
import logging
import os
from dataclasses import dataclass
from itertools import chain
from os import makedirs, mkdir, unlink
from pathlib import Path
from shutil import rmtree
from typing import Final, cast

import av
import humanize
import xxhash
from av.audio.codeccontext import AudioCodecContext
from rich.markup import escape

from albums.app import Context
from albums.config import SyncDestination
from albums.entities import Album, Track
from albums.tagger import AUDIO_FILE_SUFFIXES, AlbumTaggerProvider

logger: Final = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transcode output backends (PyAV)
#
# Transcoding is via PyAV ("av" package). Its wheels bundle precompiled
# FFmpeg shared libraries for Linux (manylinux x86_64/aarch64), macOS
# (x86_64/arm64) and Windows (amd64/arm64), so sync transcoding needs no
# system-installed ffmpeg or any other external tool.
#
# The bundled FFmpeg build (av 18.x) has:
#   encoders present: libmp3lame (MP3, CBR + VBR), native aac (M4A, CBR only),
#                     flac, libopus, pcm_* (WAV/AIFF), wmav1/wmav2, and the
#                     experimental native vorbis encoder
#   encoders missing: libvorbis, libfdk_aac, libshine - hence no Ogg Vorbis
#                     output and no true VBR AAC (see the "vbr" note below)
#   decoders: everything albums reads (flac, mp3, vorbis, aac, wma, pcm,
#             alac, opus), so every supported source format can be transcoded
#             even though some cannot be the output
#
# Notes on adding new output options later:
#   1. add the file type / bitrate to CONVERT_FILE_TYPES / CONVERT_BITRATES in
#      albums.config (this drives the config menu and the profile migration),
#   2. add the FFmpeg encoder name to _AV_ENCODERS below,
#   3. extend _setup_encoder() with the encoder's options,
#   4. add a label case to convert_bitrate_label() in albums.config, and
#   5. add a round-trip test (tests generate real audio; see AudioSpec).
#
# Encoder option mechanics:
#   * CBR: codec_context.bit_rate = <bps> before the first encode. Both
#     libmp3lame and the native aac encoder honor it. (The bit_rate getter
#     returns None when unset.)
#   * MP3 VBR: set codec_context.qscale = True and
#     codec_context.global_quality = Q where Q is LAME's VBR quality
#     0 (best, ~245-265 kbps) .. 9 (worst, ~20-30 kbps); Q=2
#     (~170-215 kbps on typical music) is what the "vbr" option means and
#     matches the old `ffmpeg -q:a 2`.
#     PyAV 18+ stores global_quality in lambda units (property value *
#     FF_QP2LAMBDA, i.e. * 256) and FFmpeg 8's libmp3lame reads
#     lame_set_VBR_quality(global_quality / FF_QP2LAMBDA), so the PyAV
#     property value maps 1:1 to the LAME quality number. Do NOT multiply by
#     64 (the old FF_QSCALE_SCALE): quality 2*64=128 clamps to the worst
#     LAME quality (silently producing ~65 kbps instead of ~190 kbps).
#   * The aac encoder apparently has no VBR mode (qscale/global_quality are
#     ignored), which is why m4a offers CBR bitrates only.
#   * codec_context.options is a dict applied by avcodec_open2, but UNKNOWN
#     option names are silently ignored (no error) - so verify names against
#     codec_context.supported_options. Two entries of note:
#       - "request_sample_fmt": "s32" on a *decoder* context makes the flac
#         decoder yield 24-bit frames (it negotiates S16 by default). Not
#         needed today because flac output is intentionally 16-bit, but this
#         is how to change that.
#       - "strict": "-2" (strict_std_compliance = FF_COMPLIANCE_EXPERIMENTAL)
#         allows experimental codecs such as the native vorbis encoder (used
#         by test fixtures to generate .ogg sources). Note the AVOption name
#         is "strict", not "strict_std_compliance".
#   * Frames: always iterate the decode generator lazily - list()-ing a whole
#     track would hold ~100 MB of samples in RAM. av.AudioResampler handles
#     sample-rate conversion, channel downmix (e.g. 5.1 -> stereo) and sample
#     format conversion; resample(frame) yields a list of frames and
#     resample(None) flushes. Output is fixed at 16-bit ("s16") for all three
#     file types: the bundled flac decoder negotiates S16 even for 24-bit
#     files, and 16-bit flac output is the desired behavior.
# ---------------------------------------------------------------------------

# FFmpeg encoder name for each transcode output file type (see module docstring above).
_AV_ENCODERS: Final = {
    "mp3": "libmp3lame",
    "m4a": "aac",
    "flac": "flac",
}


def _setup_encoder(codec_context: AudioCodecContext, file_type: str, bitrate: str) -> None:
    """Apply the destination's (file_type, bitrate) options to the output encoder; see the module docstring above."""
    if file_type == "mp3":
        if bitrate == "vbr":
            codec_context.qscale = True
            codec_context.global_quality = 2  # LAME VBR quality 2 ~= 170-215 kbps (see module docstring)
        else:
            codec_context.bit_rate = int(bitrate) * 1000
    elif file_type == "m4a":
        # native aac encoder is CBR-only (no VBR in the bundled FFmpeg)
        codec_context.bit_rate = int(bitrate) * 1000
    # flac: lossless, nothing to set


@dataclass
class CacheStat:
    """Name, total size and last-modified timestamp of a transcoder cache; orders by timestamp (oldest first)."""

    name: str
    size: int
    timestamp: int

    def __lt__(self, other: CacheStat):
        return self.timestamp < other.timestamp


# Single shared view of every profile cache on disk (name -> stats). Deliberately global, not
# per-instance: shrink_cache() must see other profiles' caches in order to evict the oldest
# one. Every value derives from the on-disk cache, so no two instances can disagree.
_global_cache_stats: dict[str, CacheStat] = {}


class Transcoder:
    """Transcode tracks on demand into a per-output cache, shrinking older output caches to fit the configured size."""

    ctx: Context
    file_type: str
    initialized = False

    _tagger: AlbumTaggerProvider
    _dest: SyncDestination
    _this_cache: Path
    _descriptor: str

    def __init__(self, ctx: Context, dest: SyncDestination):
        self.ctx = ctx
        self._dest = dest
        self.file_type = dest.convert_file_type
        # per-output cache directory key, e.g. "mp3:vbr", "m4a:192", "flac" - it changes when
        # the destination's transcode options change, which intentionally invalidates the cache
        self._descriptor = f"{dest.convert_file_type}:{dest.convert_bitrate}" if dest.convert_bitrate else dest.convert_file_type
        self._tagger = AlbumTaggerProvider(ctx.config.library, id3v1=ctx.config.id3v1)
        self._this_cache = self.ctx.config.transcoder_cache / xxhash.xxh3_64_hexdigest(self._descriptor.encode("utf-8"))

    def in_cache(self, album: Album, track: Track) -> Path | None:
        """Return the cached transcoded path for a track if it exists, else ``None``."""
        self._initialize()
        cache_path = self._cache_path(album.path, track.filename)
        return cache_path if cache_path.exists() else None

    def get_transcoded(self, album: Album, track: Track) -> Path:
        """Return the cached transcoded path for a track, transcoding it first if not already cached."""
        self._initialize()
        cache_path = self._cache_path(album.path, track.filename)
        if cache_path.exists():
            return cache_path

        makedirs(self._this_cache / album.path, exist_ok=True)
        self._transcode(self.ctx.config.library / album.path, track, cache_path)
        _global_cache_stats[self._this_cache.name].size += cache_path.stat().st_size if cache_path.exists() else 0
        return cache_path

    def shrink_cache(self):
        """Delete entire older output caches until the total cache size fits the configured maximum."""
        if sum(c.size for c in _global_cache_stats.values()) == 0:
            self._scan_cache()
        cache_max = self.ctx.config.transcoder_cache_size
        while len(_global_cache_stats) > 1 and sum(c.size for c in _global_cache_stats.values()) > cache_max:
            oldest_other_cache = next((cache for cache in sorted(_global_cache_stats.values()) if cache.name != self._this_cache.name))
            logger.info(f"deleting {humanize.naturalsize(oldest_other_cache.size, binary=True)} transcoder cache {oldest_other_cache.name}")
            rmtree(self.ctx.config.transcoder_cache / oldest_other_cache.name)
            del _global_cache_stats[oldest_other_cache.name]
            index = dict((k, v) for k, v in self._load_cache_index().items() if v != oldest_other_cache.name)
            self._update_cache_index(index)
        if (total_cache_size := sum(c.size for c in _global_cache_stats.values())) > cache_max:
            logger.warning(
                f"after deleting all but the most recently used profile, the transcoder cache size still exceeds configuration: {humanize.naturalsize(total_cache_size, binary=True)}"
            )

    def _cache_path(self, album_path: str, source_filename: str) -> Path:
        return (self._this_cache / album_path / source_filename).with_suffix(f".{self.file_type}")

    def _transcode(self, album_path: Path, track: Track, dest: Path):
        source = album_path / track.filename
        try:
            with av.open(str(source)) as src:
                streams = src.streams.audio
                if not streams:
                    raise RuntimeError(f"no audio stream in {str(source)}")
                src_stream = streams[0]
                # output sample rate: capped by the destination's max_sample_rate, else the source rate
                max_rate = self._dest.max_sample_rate
                out_rate = src_stream.rate if not max_rate or src_stream.rate <= max_rate else max_rate
                # downmix anything wider than stereo to stereo; keep mono
                out_layout = "stereo" if src_stream.layout.nb_channels > 1 else "mono"
                with av.open(str(dest), "w") as dst:
                    # the add_stream overloads resolve to a stream union for dynamic codec names; it is always audio here
                    # (PyAV stubs are partially unknown throughout - hence the ignores on this block)
                    out_stream = cast(av.AudioStream, dst.add_stream(_AV_ENCODERS[self.file_type], rate=out_rate, layout=out_layout))  # pyright: ignore[reportUnknownMemberType]
                    _setup_encoder(out_stream.codec_context, self.file_type, self._dest.convert_bitrate)
                    resampler = av.AudioResampler(format="s16", layout=out_layout, rate=out_rate)
                    for frame in chain(src.decode(src_stream), [None]):
                        for resampled in resampler.resample(frame):
                            for packet in out_stream.encode(resampled):  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                                dst.mux(packet)  # pyright: ignore[reportUnknownMemberType]
                    for packet in out_stream.encode(None):  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                        dst.mux(packet)  # pyright: ignore[reportUnknownMemberType]
        except Exception as ex:  # a per-file failure is reported and aborts the sync, not a PyAV internals traceback
            logger.error(f"failed to transcode {str(source)}: {ex}")
            raise SystemExit(1)

        if track.fields or track.pictures:
            with self._tagger.get(dest.parent).open(dest.name) as dest_fields:
                for field, value in track.field_dict().items():
                    dest_fields.set_field(field, value)
                if track.pictures:
                    with self._tagger.get(album_path).open(track.filename) as src_tags:
                        for pic, image_data in src_tags.get_pictures():
                            dest_fields.add_picture(pic, image_data)

    def _initialize(self):
        if self.initialized:
            return

        with self.ctx.console.status("Initializing transcoder cache", spinner="bouncingBar"):
            self._create_root_cache()
            self._create_this_cache()
            self._scan_cache()
            self.shrink_cache()

        self.initialized = True

    def _create_root_cache(self):
        cache = self.ctx.config.transcoder_cache
        if cache.exists() and not cache.is_dir():
            raise RuntimeError(f"transcoder cache exists but is not a directory: {str(cache)}")
        if not cache.exists():
            self.ctx.console.print(f"Creating transcoder cache: {escape(str(cache))}")
            mkdir(cache)

    def _create_this_cache(self):
        if self._this_cache.exists() and not self._this_cache.is_dir():
            raise RuntimeError(f"exists but not a directory: {str(self._this_cache)}")
        if self._this_cache.exists():
            self._this_cache.touch()
        else:
            mkdir(self._this_cache)
            self._update_cache_index()

    def _update_cache_index(self, index: dict[str, str] | None = None):
        if index is None:
            index = self._load_cache_index()
            index[self._descriptor] = self._this_cache.name
        (self.ctx.config.transcoder_cache / "index.json").write_text(json.dumps(index), encoding="utf-8")

    def _load_cache_index(self) -> dict[str, str]:
        index_file = self.ctx.config.transcoder_cache / "index.json"
        return json.loads(index_file.read_text()) if index_file.exists() else {}

    def _scan_cache(self):
        index = self._load_cache_index()
        cache_dirs = set(index.values())
        for entry in self.ctx.config.transcoder_cache.iterdir():
            if entry.is_dir():
                if entry.name in cache_dirs:
                    cache_size = self._scan_profile_cache(entry)
                    _global_cache_stats[entry.name] = CacheStat(entry.name, cache_size, int(entry.stat().st_mtime))
                else:
                    self.ctx.console.print(f"removing unknown cache dir: {escape(entry.name)}")
                    rmtree(entry)
            elif entry.name != "index.json":
                self.ctx.console.print(f"removing unknown file from cache root: {escape(entry.name)}")
                unlink(entry)
        # drop stale stats for cache dirs that no longer exist on disk (stats must always derive from disk)
        for name in list(_global_cache_stats):
            if not (self.ctx.config.transcoder_cache / name).is_dir():
                del _global_cache_stats[name]

    def _scan_profile_cache(self, cache: Path) -> int:
        size_bytes = 0
        for path in chain(iter(["."]), glob.iglob("**/", root_dir=cache, recursive=True)):
            library_path = self.ctx.config.library / path
            if library_path.is_dir():
                size_bytes += self._scan_cache_dir(cache, path, library_path)
            else:
                logger.info(f"removing unknown folder, cache {cache.name}: {escape(path)}")
                rmtree(cache / path)
        return size_bytes

    def _scan_cache_dir(self, cache: Path, path: str, library_path: Path) -> int:
        size_bytes = 0
        for entry in (cache / path).iterdir():
            if entry.is_dir():
                continue
            library_match = next(
                (
                    library_track
                    for library_track in library_path.glob(f"{entry.stem}.*")
                    if (library_track.stem == entry.stem and library_track.suffix in AUDIO_FILE_SUFFIXES)
                ),
                None,
            )
            if library_match is not None:
                stat = entry.stat()
                if (library_match.stat().st_mtime - 1.0) < stat.st_mtime:
                    size_bytes += stat.st_size  # keep for now
                else:
                    logger.debug(f"delete from cache, library file newer: {path}{os.sep}{entry.name}")
                    unlink(entry)  # older than library file
            else:
                logger.debug(f"delete from cache, not in library: {path}{os.sep}{entry.name}")
                unlink(entry)  # not in library any more

        return size_bytes
