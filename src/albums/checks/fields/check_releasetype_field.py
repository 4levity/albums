from albums.tagger.types import BasicField

from ..base_check_field_per_album import BaseCheckFieldPerAlbum


class CheckReleaseTypeField(BaseCheckFieldPerAlbum):
    name = "release-type-field"
    field = BasicField.RELEASETYPE
    vorbis_only = True
    tuple_value = True
