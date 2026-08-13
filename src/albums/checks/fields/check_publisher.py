from albums.checks.base_check_field_per_album import BaseCheckFieldPerAlbum
from albums.tagger.types import BasicField


class CheckPublisherField(BaseCheckFieldPerAlbum):
    name = "publisher"
    field = BasicField.ORGANIZATION
    field_description = "publisher/organization"
    must_pass_checks = {"legacy-fields"}
