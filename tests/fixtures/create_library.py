import array
import io
import math
import os
import shutil
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Collection, Mapping, Set, cast

import av
from PIL import Image

from albums.entities import Album, Track, TrackPicture
from albums.picture import mime_type_to_format
from albums.tagger import LEGACY_ID3_FIELDS, LEGACY_VORBIS_FIELDS, AlbumTagger, BasicField, Picture

from .empty_files import (
    EMPTY_AIFF_FILE_BYTES,
    EMPTY_FLAC_FILE_BYTES,
    EMPTY_M4A_FILE_BYTES,
    EMPTY_MP3_FILE_BYTES,
    EMPTY_MP4_VIDEO_FILE_BYTES,
    EMPTY_OGG_VORBIS_FILE_BYTES,
    EMPTY_WMA_FILE_BYTES,
)

# legacy field names (Vorbis comment names and deprecated ID3 frames) to their canonical BasicField
LEGACY_TAG_MAP: Mapping[str, BasicField] = dict(LEGACY_VORBIS_FIELDS) | dict(LEGACY_ID3_FIELDS)

# Gitignored scratch area for generated fixtures and the DB snapshot cache (helpers.init_db_cached).
# Paths must stay stable: snapshot databases embed the library's absolute location.
test_tmp_dir = Path(__file__).resolve().parent.parent / "tmp"


@dataclass(frozen=True)
class AudioSpec:
    """Parameters for real audio test files (a deterministic sine tone)."""

    seconds: int = 1
    sample_rate: int = 44100
    channels: int = 2  # 1 = mono, 2 = stereo, 6 = 5.1
    bits: int = 16


# FFmpeg encoder name and CBR bitrate for real audio test files, per extension. The ".ogg"
# encoder (native vorbis) is experimental in the bundled FFmpeg build - see create_audio_file.
_AUDIO_FILE_CODECS: Mapping[str, tuple[str, int | None]] = {
    ".flac": ("flac", None),
    ".mp3": ("libmp3lame", 128_000),
    ".m4a": ("aac", 128_000),
    ".ogg": ("vorbis", 128_000),
    ".wma": ("wmav2", 128_000),
    ".aiff": ("pcm_s16le", None),
}


def create_audio_file(path: Path, spec: AudioSpec = AudioSpec(), frequency: float = 440.0):
    """Create a small real audio file (deterministic sine tone) that tests can decode or transcode."""
    (encoder, bitrate) = _AUDIO_FILE_CODECS[path.suffix]
    layout = {1: "mono", 2: "stereo", 6: "5.1"}[spec.channels]
    sample_format = "s16" if spec.bits <= 16 else "s32"
    samples_per_channel = int(spec.seconds * spec.sample_rate)
    amplitude = 32767 if spec.bits <= 16 else 2147483647
    channels = [array.array("h" if spec.bits <= 16 else "i") for _ in range(spec.channels)]
    for i in range(samples_per_channel * spec.channels):
        value = int(math.sin(2 * math.pi * frequency * (i % spec.sample_rate) / spec.sample_rate) * 0.25 * amplitude)
        channels[i % spec.channels].append(value)
    with av.open(str(path), "w") as container:
        # the add_stream overloads resolve to a stream union for dynamic codec names; it is always audio here
        stream = cast(av.AudioStream, container.add_stream(encoder, rate=spec.sample_rate, layout=layout))
        codec_context = stream.codec_context
        if encoder == "vorbis":
            # the bundled FFmpeg's native vorbis encoder is experimental; the "strict" AVOption
            # (strict_std_compliance = -2) enables it. Unknown option names are silently
            # ignored by avcodec_open2 - "strict" (not "strict_std_compliance") is the real name
            codec_context.options = {"strict": "-2"}
        if bitrate:
            codec_context.bit_rate = bitrate
        frame = av.AudioFrame(format=sample_format, layout=layout, samples=samples_per_channel)
        frame.sample_rate = spec.sample_rate
        frame.time_base = Fraction(1, spec.sample_rate)
        frame.pts = 0
        if sample_format.endswith("p"):  # planar: one plane per channel
            for channel in range(spec.channels):
                frame.planes[channel].update(channels[channel].tobytes())
        else:  # packed: single interleaved plane
            interleaved = bytearray()
            for i in range(samples_per_channel):
                for channel in range(spec.channels):
                    interleaved += bytes(channels[channel][i : i + 1])
            frame.planes[0].update(bytes(interleaved))
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)


def create_track_file(path: Path, spec: Track, audio: AudioSpec | None = None):
    filename: Path = path / spec.filename
    if audio is not None:
        create_audio_file(filename, audio)
    else:
        with open(filename, "wb") as file:
            if filename.suffix == ".flac":
                file.write(EMPTY_FLAC_FILE_BYTES)
            elif filename.suffix in {".m4a", ".m4b", ".mp4"}:
                file.write(EMPTY_M4A_FILE_BYTES)
            elif filename.suffix == ".mp3":
                file.write(EMPTY_MP3_FILE_BYTES)
            elif filename.suffix == ".wma":
                file.write(EMPTY_WMA_FILE_BYTES)
            elif filename.suffix == ".ogg":
                file.write(EMPTY_OGG_VORBIS_FILE_BYTES)
            elif filename.suffix == ".aiff":
                file.write(EMPTY_AIFF_FILE_BYTES)
    if spec.fields or spec.pictures:
        tagger = AlbumTagger(path, padding=lambda _: 0)
        with tagger.open(spec.filename) as tag:
            for pic in spec.pictures:
                image_data = make_image_data(pic.picture_info.width, pic.picture_info.height, mime_type_to_format(pic.picture_info.mime_type))
                picture = Picture(pic.picture_info, pic.picture_type, pic.description) if isinstance(pic, TrackPicture) else pic
                tag.add_picture(picture, image_data)
            spec_tags = spec.fields
            represented_by_legacy_fields: Set[BasicField] = set()
            for field_name in spec.legacy_fields:
                basic_field = LEGACY_TAG_MAP[field_name]
                tag.set_field(field_name, spec_tags[basic_field])
                represented_by_legacy_fields.add(basic_field)
            for field_name, values in spec_tags.items():
                if field_name not in represented_by_legacy_fields:
                    tag.set_field(field_name, list(values))


def create_picture_file(path: Path, width: int = 400, height: int = 400, color: str = "blue"):
    image = Image.new("RGB", (width, height), color=color)
    image.save(path)


def create_other_file(path: Path):
    with open(path, "wb") as file:
        if path.suffix == ".mp4":
            file.write(EMPTY_MP4_VIDEO_FILE_BYTES)


def create_album_in_library(library_path: Path, album: Album, audio: AudioSpec | None = None):
    path = library_path / album.path
    os.makedirs(path)
    for track in album.tracks:
        create_track_file(path, track, audio)
    for file in album.picture_files:
        create_picture_file(path / file.filename, file.picture_info.width, file.picture_info.height)
    for other in album.other_files:
        create_other_file(path / other.filename)


def create_library(library_name: str, albums: Collection[Album], audio: AudioSpec | None = None):
    library_path = test_tmp_dir / library_name
    if library_path.exists():
        shutil.rmtree(library_path)
    os.makedirs(library_path)
    for album in albums:
        create_album_in_library(library_path, album, audio)
    return library_path


def make_image_data(width: int = 400, height: int = 400, format: str = "PNG", color: str = "blue") -> bytes:
    image = Image.new("RGB", (width, height), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format)
    return buffer.getvalue()
