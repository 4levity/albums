from albums.checks.base_check_field_per_album import BaseCheckFieldPerAlbum
from albums.tagger import BasicField


class CheckReleaseCountryField(BaseCheckFieldPerAlbum):
    name = "release-country"
    field = BasicField.RELEASECOUNTRY
    vorbis_only = True
