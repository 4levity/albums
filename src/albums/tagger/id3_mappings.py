from typing import Final, Tuple

from albums.tagger.types import BasicTag

BASIC_ID3_TEXT_FRAMES: Final[Tuple[Tuple[BasicTag, str], ...]] = (
    (BasicTag.ALBUM, "TALB"),
    (BasicTag.ALBUMSORT, "TSOA"),
    (BasicTag.ALBUMARTIST, "TPE2"),
    (BasicTag.ALBUMARTISTSORT, "TSO2"),
    (BasicTag.ARTIST, "TPE1"),
    (BasicTag.ARTISTSORT, "TSOP"),
    (BasicTag.BARCODE, "TXXX:BARCODE"),
    (BasicTag.COMPILATION, "TCMP"),
    (BasicTag.MUSICBRAINZ_ALBUMARTISTID, "TXXX:MusicBrainz Album Artist Id"),
    (BasicTag.MUSICBRAINZ_ALBUMID, "TXXX:MusicBrainz Album Id"),
    (BasicTag.MUSICBRAINZ_ALBUMRELEASECOUNTRY, "TXXX:MusicBrainz Album Release Country"),
    (BasicTag.MUSICBRAINZ_ALBUMRELEASETYPE, "TXXX:MusicBrainz Album Release Type"),
    (BasicTag.MUSICBRAINZ_ARRANGERID, "TXXX:MusicBrainz Arranger Id"),
    (BasicTag.MUSICBRAINZ_ARTISTID, "TXXX:MusicBrainz Artist Id"),
    (BasicTag.MUSICBRAINZ_COMPOSERID, "TXXX:MusicBrainz Composer Id"),
    (BasicTag.MUSICBRAINZ_CONDUCTORID, "TXXX:MusicBrainz Conductor Id"),
    (BasicTag.MUSICBRAINZ_DIRECTORID, "TXXX:MusicBrainz Director Id"),
    (BasicTag.MUSICBRAINZ_DISCID, "TXXX:MusicBrainz Disc Id"),
    (BasicTag.MUSICBRAINZ_LYRICISTID, "TXXX:MusicBrainz Lyricist Id"),
    (BasicTag.MUSICBRAINZ_MIXERID, "TXXX:MusicBrainz Mixer Id"),
    (BasicTag.MUSICBRAINZ_ORIGINALALBUMID, "TXXX:MusicBrainz Original Album Id"),
    (BasicTag.MUSICBRAINZ_ORIGINALARTISTID, "TXXX:MusicBrainz Original Artist Id"),
    (BasicTag.MUSICBRAINZ_ORIGINALRELEASEID, "TXXX:MusicBrainz Original Release Id"),
    (BasicTag.MUSICBRAINZ_PRODUCERID, "TXXX:MusicBrainz Producer Id"),
    (BasicTag.MUSICBRAINZ_RELEASEARTISTID, "TXXX:MusicBrainz Release Artist Id"),
    (BasicTag.MUSICBRAINZ_RELEASEGROUPID, "TXXX:MusicBrainz Release Group Id"),
    (BasicTag.MUSICBRAINZ_RELEASETRACKID, "TXXX:MusicBrainz Release Track Id"),
    (BasicTag.MUSICBRAINZ_REMIXERID, "TXXX:MusicBrainz Remixer Id"),
    # also UFID:http://musicbrainz.org is track id / musicbrainz_recordingid
    (BasicTag.MUSICBRAINZ_TRMID, "TXXX:MusicBrainz TRM Id"),
    (BasicTag.MUSICBRAINZ_WORKID, "TXXX:MusicBrainz Work Id"),
    (BasicTag.ORGANIZATION, "TPUB"),
    # nonstandard: this tagger will read and remove it but will not set it
    (BasicTag.RELEASECOUNTRY, "TXXX:RELEASECOUNTRY"),  # nonstandard
    (BasicTag.RELEASETYPE, "TXXX:RELEASETYPE"),  # nonstandard
    #
    (BasicTag.TITLE, "TIT2"),
    # TCON too but we use .genres instead of .text
    # TRCK and TPOS too but they are not 1:1
)


# TODO also pull other common values, like
# "composer": "tcom",
# "encoder": "tenc",
# "date": "tdrc",  # recordingdate?

UFID_MUSICBRAINZ_OWNER: Final = "http://musicbrainz.org"

TAG_TO_ID3_TEXT_FRAME: Final = dict(BASIC_ID3_TEXT_FRAMES)
