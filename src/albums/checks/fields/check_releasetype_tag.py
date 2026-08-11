from albums.tagger.types import BasicField

from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckReleaseTypeTag(BaseCheckTagPerAlbum):
    name = "release-type-tag"
    tag = BasicField.RELEASETYPE
    vorbis_only = True
    tuple_value = True
