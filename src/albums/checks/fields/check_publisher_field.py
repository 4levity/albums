from ...tagger.types import BasicField
from ..base_check_field_per_album import BaseCheckFieldPerAlbum


class CheckPublisherField(BaseCheckFieldPerAlbum):
    name = "publisher-field"
    field = BasicField.ORGANIZATION
    field_description = "publisher/organization"
    must_pass_checks = {"legacy-tags"}
