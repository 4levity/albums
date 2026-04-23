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


class BasicTag(StrEnum):
    # BasicTag names must be the same as the corresponding Vorbis Comment names

    ALBUM = auto()
    ALBUMARTIST = auto()
    ARTIST = auto()
    DISCNUMBER = auto()
    DISCTOTAL = auto()
    GENRE = auto()
    OLD_ALBUM_ARTIST = "album artist"  # incorrect tag "album artist" - correct is "albumartist"
    ORGANIZATION = auto()  # Publisher, record label
    TITLE = auto()
    TRACKNUMBER = auto()
    TRACKTOTAL = auto()

    # TXXX:MusicBrainz Album Artist Id, ----:com.apple.iTunes:MusicBrainz Album Artist Id, MusicBrainz/Album Artist Id
    MUSICBRAINZ_ALBUMARTISTID = auto()

    # TXXX:MusicBrainz Album Id, ----:com.apple.iTunes:MusicBrainz Album Id, MusicBrainz/Album Id
    MUSICBRAINZ_ALBUMID = auto()

    # TXXX:MusicBrainz Artist Id, ----:com.apple.iTunes:MusicBrainz Artist Id, MusicBrainz/Artist Id
    MUSICBRAINZ_ARTISTID = auto()

    # TXXX:MusicBrainz Composer Id, ----:com.apple.iTunes:MusicBrainz Composer Id, MusicBrainz/Composer Id
    MUSICBRAINZ_COMPOSERID = auto()

    # TXXX:MusicBrainz Disc Id, ----:com.apple.iTunes:MusicBrainz Disc Id, MusicBrainz/Disc Id
    MUSICBRAINZ_DISCID = auto()

    # TXXX:MusicBrainz Original Album Id, ----:com.apple.iTunes:MusicBrainz Original Album Id, MusicBrainz/Original Album Id
    MUSICBRAINZ_ORIGINALALBUMID = auto()

    # TXXX:MusicBrainz Original Artist Id, ----:com.apple.iTunes:MusicBrainz Original Artist Id, MusicBrainz/Original Artist Id
    MUSICBRAINZ_ORIGINALARTISTID = auto()

    # (aka musicbrainz_recordingid) UFID:http://musicbrainz.org, ----:com.apple.iTunes:MusicBrainz Track Id, MusicBrainz/Track Id
    MUSICBRAINZ_TRACKID = auto()

    # (deprecated) TXXX:MusicBrainz TRM Id, ----:com.apple.iTunes:MusicBrainz TRM Id, MusicBrainz/TRM Id
    MUSICBRAINZ_TRMID = auto()

    # TXXX:MusicBrainz Release Group Id, ----:com.apple.iTunes:MusicBrainz Release Group Id, MusicBrainz/Release Group Id
    MUSICBRAINZ_RELEASEGROUPID = auto()

    # (aka musicbrainz_trackid) TXXX:MusicBrainz Release Track Id, ----:com.apple.iTunes:MusicBrainz Release Track Id, MusicBrainz/Release Track Id
    MUSICBRAINZ_RELEASETRACKID = auto()

    # TXXX:MusicBrainz Work Id, ----:com.apple.iTunes:MusicBrainz Work Id, MusicBrainz/Work Id
    MUSICBRAINZ_WORKID = auto()


BASIC_TAGS: Final = frozenset(tag.value for tag in BasicTag)

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
    """
    ID3 picture type, also used with other tag systems
    """

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
        if any(match in str.lower(filename) for match in ["folder", ".folder", "cover", "album", "front", "thumbnail"]):
            return PictureType.COVER_FRONT
        return PictureType.OTHER


@dataclass(frozen=True)
class Picture:
    picture_info: PictureInfo
    type: PictureType
    description: str


@dataclass(frozen=True)
class StreamInfo:
    length: float = 0.0
    bitrate: int = 0
    channels: int = 0
    codec: str = "unknown"
    sample_rate: int = 0
    error: str = ""

    def to_dict(self):
        result = self.__dict__
        if not self.error:
            del result["error"]
        return result


@dataclass(frozen=True)
class ScanResult:
    tags: Tuple[Tuple[BasicTag, Tuple[str, ...]], ...]
    pictures: Tuple[Picture, ...]
    stream: StreamInfo


class TaggerFile:
    def scan(self) -> ScanResult: ...
    def get_image_data(self, picture: Picture) -> bytes: ...
    def get_pictures(self) -> Generator[Tuple[Picture, bytes], None, None]: ...
    def has_video(self) -> bool: ...

    def set_tag(self, tag: BasicTag, value: str | List[str] | None) -> None: ...
    def add_picture(self, new_picture: Picture, image_data: bytes) -> None: ...
    def remove_picture(self, remove_picture: Picture) -> None: ...
    def close(self) -> None: ...
