from ...types import BasicTag
from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckReleaseCountryTag(BaseCheckTagPerAlbum):
    name = "release-country-tag"
    tag = BasicTag.RELEASECOUNTRY
    vorbis_only = True
