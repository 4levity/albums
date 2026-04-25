from ...types import BasicTag
from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckAlbumArtistSort(BaseCheckTagPerAlbum):
    name = "album-artist-sort"
    tag = BasicTag.ALBUMARTISTSORT
    tag_description = "album-artist sort order"

    # TODO: check or generate sort order tag
