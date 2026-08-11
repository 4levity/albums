from albums.tagger.types import BasicField

from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckReleaseCountryTag(BaseCheckTagPerAlbum):
    name = "release-country-tag"
    tag = BasicField.RELEASECOUNTRY
    vorbis_only = True
