from albums.tagger.types import BasicField

from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckAlbumSort(BaseCheckTagPerAlbum):
    name = "album-sort"
    tag = BasicField.ALBUMSORT
    tag_description = "album sort order"

    # TODO: check or generate sort order tag
