from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum, StrEnum, auto
from typing import Final, Generator, List, Tuple

from mutagen.aac import AAC
from mutagen.ac3 import AC3
from mutagen.aiff import AIFF
from mutagen.apev2 import APEv2File
from mutagen.asf import ASF
from mutagen.dsdiff import DSDIFF
from mutagen.dsf import DSF
from mutagen.easyid3 import EasyID3FileType
from mutagen.easymp4 import EasyMP4
from mutagen.flac import FLAC
from mutagen.id3 import ID3FileType
from mutagen.monkeysaudio import MonkeysAudio
from mutagen.mp3 import MP3, EasyMP3
from mutagen.mp4 import MP4
from mutagen.musepack import Musepack
from mutagen.oggflac import OggFLAC
from mutagen.oggopus import OggOpus
from mutagen.oggspeex import OggSpeex
from mutagen.oggtheora import OggTheora
from mutagen.oggvorbis import OggVorbis
from mutagen.optimfrog import OptimFROG
from mutagen.smf import SMF
from mutagen.tak import TAK
from mutagen.trueaudio import EasyTrueAudio, TrueAudio
from mutagen.wave import WAVE
from mutagen.wavpack import WavPack

from ..picture.info import PictureInfo


class BasicField(StrEnum):
    """Standard metadata fields supported across audio formats.

    BasicField values must be the same as the corresponding Vorbis Comment field names.
    """

    ALBUM = auto()
    ALBUMSORT = auto()
    ALBUMARTIST = auto()
    ALBUMARTISTSORT = auto()
    ARTIST = auto()
    ARTISTSORT = auto()
    BARCODE = auto()
    COMPILATION = auto()
    DISCNUMBER = auto()
    DISCTOTAL = auto()
    GENRE = auto()

    ORGANIZATION = auto()  # Publisher, record label
    RELEASECOUNTRY = auto()  # vorbis comment only (MUSICBRAINZ_ALBUMRELEASECOUNTRY is probably preferred)
    RELEASETYPE = auto()  # vorbis comment only (MUSICBRAINZ_ALBUMRELEASETYPE is probably preferred)
    TITLE = auto()
    TRACKNUMBER = auto()
    TRACKTOTAL = auto()

    # TXXX:MusicBrainz Album Artist Id, ----:com.apple.iTunes:MusicBrainz Album Artist Id, MusicBrainz/Album Artist Id
    MUSICBRAINZ_ALBUMARTISTID = auto()

    # TXXX:MusicBrainz Album Id, ----:com.apple.iTunes:MusicBrainz Album Id, MusicBrainz/Album Id
    MUSICBRAINZ_ALBUMID = auto()

    # TXXX:MusicBrainz Album Release Country, ----:com.apple.iTunes:MusicBrainz Album Release Country, MusicBrainz/Album Release Country
    MUSICBRAINZ_ALBUMRELEASECOUNTRY = auto()

    # TXXX:MusicBrainz Album Release Type, ----:com.apple.iTunes:MusicBrainz Album Release Type, MusicBrainz/Album Release Type
    MUSICBRAINZ_ALBUMRELEASETYPE = auto()

    # TXXX:MusicBrainz Arranger Id, ----:com.apple.iTunes:MusicBrainz Arranger Id, MusicBrainz/Arranger Id
    MUSICBRAINZ_ARRANGERID = auto()

    # TXXX:MusicBrainz Artist Id, ----:com.apple.iTunes:MusicBrainz Artist Id, MusicBrainz/Artist Id
    MUSICBRAINZ_ARTISTID = auto()

    # TXXX:MusicBrainz Composer Id, ----:com.apple.iTunes:MusicBrainz Composer Id, MusicBrainz/Composer Id
    MUSICBRAINZ_COMPOSERID = auto()

    # TXXX:MusicBrainz Conductor Id, ----:com.apple.iTunes:MusicBrainz Conductor Id, MusicBrainz/Conductor Id
    MUSICBRAINZ_CONDUCTORID = auto()

    # TXXX:MusicBrainz Director Id, ----:com.apple.iTunes:MusicBrainz Director Id, MusicBrainz/Director Id
    MUSICBRAINZ_DIRECTORID = auto()

    # TXXX:MusicBrainz Disc Id, ----:com.apple.iTunes:MusicBrainz Disc Id, MusicBrainz/Disc Id
    MUSICBRAINZ_DISCID = auto()

    # TXXX:MusicBrainz Lyricist Id, ----:com.apple.iTunes:MusicBrainz Lyricist Id, MusicBrainz/Lyricist Id
    MUSICBRAINZ_LYRICISTID = auto()

    # TXXX:MusicBrainz Mixer Id, ----:com.apple.iTunes:MusicBrainz Mixer Id, MusicBrainz/Mixer Id
    MUSICBRAINZ_MIXERID = auto()

    # TXXX:MusicBrainz Original Album Id, ----:com.apple.iTunes:MusicBrainz Original Album Id, MusicBrainz/Original Album Id
    MUSICBRAINZ_ORIGINALALBUMID = auto()

    # TXXX:MusicBrainz Original Artist Id, ----:com.apple.iTunes:MusicBrainz Original Artist Id, MusicBrainz/Original Artist Id
    MUSICBRAINZ_ORIGINALARTISTID = auto()

    # TXXX:MusicBrainz Original Release Id, ----:com.apple.iTunes:MusicBrainz Original Release Id, MusicBrainz/Original Release Id
    MUSICBRAINZ_ORIGINALRELEASEID = auto()

    # TXXX:MusicBrainz Producer Id, ----:com.apple.iTunes:MusicBrainz Producer Id, MusicBrainz/Producer Id
    MUSICBRAINZ_PRODUCERID = auto()

    # (aka musicbrainz_recordingid) UFID:http://musicbrainz.org, ----:com.apple.iTunes:MusicBrainz Track Id, MusicBrainz/Track Id
    MUSICBRAINZ_TRACKID = auto()

    # (deprecated) TXXX:MusicBrainz TRM Id, ----:com.apple.iTunes:MusicBrainz TRM Id, MusicBrainz/TRM Id
    MUSICBRAINZ_TRMID = auto()

    # TXXX:MusicBrainz Release Artist Id, ----:com.apple.iTunes:MusicBrainz Release Artist Id, MusicBrainz/Release Artist Id
    MUSICBRAINZ_RELEASEARTISTID = auto()

    # TXXX:MusicBrainz Release Group Id, ----:com.apple.iTunes:MusicBrainz Release Group Id, MusicBrainz/Release Group Id
    MUSICBRAINZ_RELEASEGROUPID = auto()

    # (aka musicbrainz_trackid) TXXX:MusicBrainz Release Track Id, ----:com.apple.iTunes:MusicBrainz Release Track Id, MusicBrainz/Release Track Id
    MUSICBRAINZ_RELEASETRACKID = auto()

    # TXXX:MusicBrainz Remixer Id, ----:com.apple.iTunes:MusicBrainz Remixer Id, MusicBrainz/Remixer Id
    MUSICBRAINZ_REMIXERID = auto()

    # TXXX:MusicBrainz Work Id, ----:com.apple.iTunes:MusicBrainz Work Id, MusicBrainz/Work Id
    MUSICBRAINZ_WORKID = auto()

    # This special value is never produced by reading a tag and cannot be set on any tag
    UNKNOWN = auto()


BASIC_FIELDS: Final = frozenset(tag.value for tag in BasicField)

type MutagenFileType = (
    AAC
    | AC3
    | AIFF
    | APEv2File
    | ASF
    | DSDIFF
    | DSF
    | EasyID3FileType
    | EasyMP3
    | EasyMP4
    | EasyTrueAudio
    | FLAC
    | ID3FileType
    | MP3
    | MP4
    | MonkeysAudio
    | Musepack
    | OggFLAC
    | OggOpus
    | OggSpeex
    | OggTheora
    | OggVorbis
    | OptimFROG
    | SMF
    | TAK
    | TrueAudio
    | WAVE
    | WavPack
)


class PictureType(IntEnum):
    """ID3 picture type, also used with other tag systems."""

    OTHER = 0
    FILE_ICON = 1
    OTHER_FILE_ICON = 2
    COVER_FRONT = 3
    COVER_BACK = 4
    LEAFLET_PAGE = 5
    MEDIA = 6
    LEAD_ARTIST = 7
    ARTIST = 8
    CONDUCTOR = 9
    BAND = 10
    COMPOSER = 11
    LYRICIST = 12
    RECORDING_LOCATION = 13
    DURING_RECORDING = 14
    DURING_PERFORMANCE = 15
    SCREEN_CAPTURE = 16
    FISH = 17
    ILLUSTRATION = 18
    BAND_LOGOTYPE = 19
    PUBLISHER_LOGOTYPE = 20

    @staticmethod
    def from_filename(filename: str):
        """Heuristically derive a picture type from *filename*.

        Filenames containing common cover-art terms (``folder``, ``cover``, ``album``, ``front``, ``thumbnail``) map
        to :attr:`COVER_FRONT`; everything else maps to :attr:`OTHER`.
        """
        if any(match in str.lower(filename) for match in ["folder", ".folder", "cover", "album", "front", "thumbnail"]):
            return PictureType.COVER_FRONT
        return PictureType.OTHER


@dataclass(frozen=True)
class Picture:
    """Metadata for a picture (may be embedded in a tag, or just an image file)."""

    picture_info: PictureInfo
    type: PictureType
    description: str


@dataclass(frozen=True)
class StreamInfo:
    """Describes audio stream properties like length, bitrate, and codec."""

    length: float = 0.0
    bitrate: int = 0
    channels: int = 0
    codec: str = "unknown"
    sample_rate: int = 0
    bits_per_sample: int = 0
    error: str = ""

    def to_dict(self):
        result = self.__dict__
        if not self.error:
            del result["error"]
        return result


class TaggerFile(ABC):
    """Abstract interface for reading and writing tags/images on a single media file.

    This is a base class and should not be instantiated directly. Subclasses must
    implement every abstract method. The non-abstract methods are optional hooks
    with default behavior, which subclasses may override to support video streams
    or legacy (non-standard) fields.
    """

    @abstractmethod
    def get_fields(self) -> Tuple[Tuple[BasicField, Tuple[str, ...]], ...]:
        """Return the fields present in the tag as (field, values) pairs."""
        ...

    @abstractmethod
    def get_stream_info(self) -> StreamInfo:
        """Return properties of the audio stream, like length, bitrate, and codec."""
        ...

    @abstractmethod
    def get_image_data(self, picture: Picture) -> bytes:
        """Return the image data for the given picture."""
        ...

    @abstractmethod
    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]:
        """Yield (picture, image_data) for each image associated with the file."""
        ...

    # set_field must support BasicField but may raise an exception if a str-typed field is provided
    @abstractmethod
    def set_field(self, field: BasicField | str, value: str | List[str] | None) -> None:
        """Set a field to a value, or remove the field if value is None."""
        ...

    @abstractmethod
    def add_picture(self, new_picture: Picture, image_data: bytes) -> None:
        """Add an image to the file."""
        ...

    @abstractmethod
    def remove_picture(self, remove_picture: Picture) -> None:
        """Remove an image from the file, matching the given picture."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Save any pending changes and release the file."""
        ...

    # file types that may contain video streams (e.g. mp4) should override this:
    def has_video(self) -> bool:
        return False

    # file types that may have automatically-convertible legacy fields (e.g. FLAC, Ogg Vorbis) should override these:
    def set_legacy_field(self, field: str, value: str | List[str] | None) -> None:
        raise NotImplementedError()

    def get_legacy_fields(self) -> Tuple[Tuple[str, BasicField], ...]:
        return ()


class ID3v1Policy(IntEnum):
    """Strategy for handling legacy ID3v1 tags when saving MP3 files.

    Values map directly to the numeric codes expected by ``mutagen.mp3.MP3.save``'s ``v1`` parameter.
    """

    REMOVE = 0  # Strip any existing ID3v1 tag on save.
    UPDATE = 1  # Update existing ID3v1 in-place if present; otherwise leave absent.
    CREATE = 2  # Always write an ID3v1 tag (creating one when none exists).
