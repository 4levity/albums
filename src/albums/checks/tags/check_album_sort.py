from ...types import BasicTag
from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckAlbumSort(BaseCheckTagPerAlbum):
    name = "album-sort"
    tag = BasicTag.ALBUMSORT
    tag_description = "album sort order"

    # TODO: check or generate sort order tag
