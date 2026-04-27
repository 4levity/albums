from ...types import BasicTag
from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckReleaseTypeTag(BaseCheckTagPerAlbum):
    name = "release-type-tag"
    tag = BasicTag.RELEASETYPE
    vorbis_only = True
    tuple_value = True
