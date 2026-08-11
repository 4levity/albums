from ...tagger.types import BasicField
from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckPublisherTag(BaseCheckTagPerAlbum):
    name = "publisher-tag"
    tag = BasicField.ORGANIZATION
    tag_description = "publisher/organization"
    must_pass_checks = {"legacy-tags"}
