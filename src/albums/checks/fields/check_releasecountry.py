from albums.tagger.types import BasicField

from ..base_check_field_per_album import BaseCheckFieldPerAlbum


class CheckReleaseCountryField(BaseCheckFieldPerAlbum):
    name = "release-country"
    field = BasicField.RELEASECOUNTRY
    vorbis_only = True
