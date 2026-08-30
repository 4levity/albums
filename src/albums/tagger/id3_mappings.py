from typing import Final, Tuple

from .types import BasicField

BASIC_ID3_TEXT_FRAMES: Final[Tuple[Tuple[BasicField, str], ...]] = (
    (BasicField.ALBUM, "TALB"),
    (BasicField.ALBUMSORT, "TSOA"),
    (BasicField.ALBUMARTIST, "TPE2"),
    (BasicField.ALBUMARTISTSORT, "TSO2"),
    (BasicField.ARTIST, "TPE1"),
    (BasicField.ARTISTSORT, "TSOP"),
    (BasicField.BARCODE, "TXXX:BARCODE"),
    (BasicField.COMPILATION, "TCMP"),
    (BasicField.MUSICBRAINZ_ALBUMARTISTID, "TXXX:MusicBrainz Album Artist Id"),
    (BasicField.MUSICBRAINZ_ALBUMID, "TXXX:MusicBrainz Album Id"),
    (BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY, "TXXX:MusicBrainz Album Release Country"),
    (BasicField.MUSICBRAINZ_ALBUMRELEASETYPE, "TXXX:MusicBrainz Album Release Type"),
    (BasicField.MUSICBRAINZ_ARRANGERID, "TXXX:MusicBrainz Arranger Id"),
    (BasicField.MUSICBRAINZ_ARTISTID, "TXXX:MusicBrainz Artist Id"),
    (BasicField.MUSICBRAINZ_COMPOSERID, "TXXX:MusicBrainz Composer Id"),
    (BasicField.MUSICBRAINZ_CONDUCTORID, "TXXX:MusicBrainz Conductor Id"),
    (BasicField.MUSICBRAINZ_DIRECTORID, "TXXX:MusicBrainz Director Id"),
    (BasicField.MUSICBRAINZ_DISCID, "TXXX:MusicBrainz Disc Id"),
    (BasicField.MUSICBRAINZ_LYRICISTID, "TXXX:MusicBrainz Lyricist Id"),
    (BasicField.MUSICBRAINZ_MIXERID, "TXXX:MusicBrainz Mixer Id"),
    (BasicField.MUSICBRAINZ_ORIGINALALBUMID, "TXXX:MusicBrainz Original Album Id"),
    (BasicField.MUSICBRAINZ_ORIGINALARTISTID, "TXXX:MusicBrainz Original Artist Id"),
    (BasicField.MUSICBRAINZ_ORIGINALRELEASEID, "TXXX:MusicBrainz Original Release Id"),
    (BasicField.MUSICBRAINZ_PRODUCERID, "TXXX:MusicBrainz Producer Id"),
    (BasicField.MUSICBRAINZ_RELEASEARTISTID, "TXXX:MusicBrainz Release Artist Id"),
    (BasicField.MUSICBRAINZ_RELEASEGROUPID, "TXXX:MusicBrainz Release Group Id"),
    (BasicField.MUSICBRAINZ_RELEASETRACKID, "TXXX:MusicBrainz Release Track Id"),
    (BasicField.MUSICBRAINZ_REMIXERID, "TXXX:MusicBrainz Remixer Id"),
    # also UFID:http://musicbrainz.org is track id / musicbrainz_recordingid
    (BasicField.MUSICBRAINZ_TRMID, "TXXX:MusicBrainz TRM Id"),
    (BasicField.MUSICBRAINZ_WORKID, "TXXX:MusicBrainz Work Id"),
    (BasicField.ORGANIZATION, "TPUB"),
    # nonstandard: this tagger will read and remove it but will not set it
    (BasicField.RELEASECOUNTRY, "TXXX:RELEASECOUNTRY"),
    (BasicField.RELEASETYPE, "TXXX:RELEASETYPE"),
    (BasicField.TITLE, "TIT2"),
    # TCON too but we use .genres instead of .text
    # TRCK and TPOS too but they are not 1:1
)


# TODO also pull other common values, like
# "composer": "tcom",
# "encoder": "tenc",
# "date": "tdrc",  # recordingdate?

UFID_MUSICBRAINZ_OWNER: Final = "http://musicbrainz.org"

FIELD_TO_ID3_TEXT_FRAME: Final = dict(BASIC_ID3_TEXT_FRAMES)
