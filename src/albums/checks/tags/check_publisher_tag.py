from ...types import BasicTag
from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckPublisherTag(BaseCheckTagPerAlbum):
    name = "publisher-tag"
    tag = BasicTag.ORGANIZATION
    tag_description = "publisher/organization"
