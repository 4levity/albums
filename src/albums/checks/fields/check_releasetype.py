from albums.checks.base_check_field_per_album import BaseCheckFieldPerAlbum
from albums.tagger import BasicField


class CheckReleaseTypeField(BaseCheckFieldPerAlbum):
    name = "release-type"
    field = BasicField.RELEASETYPE
    vorbis_only = True
    tuple_value = True
