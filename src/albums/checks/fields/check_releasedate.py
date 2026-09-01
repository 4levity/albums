from albums.checks.base_check_field_per_album import BaseCheckFieldPerAlbum
from albums.tagger import BasicField


class CheckReleaseDateField(BaseCheckFieldPerAlbum):
    name = "release-date"
    field = BasicField.DATE
    field_description = "release date"
