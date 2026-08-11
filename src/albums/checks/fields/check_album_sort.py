from albums.tagger.types import BasicField

from ..base_check_field_per_album import BaseCheckFieldPerAlbum


class CheckAlbumSort(BaseCheckFieldPerAlbum):
    name = "album-sort"
    field = BasicField.ALBUMSORT
    field_description = "album sort order"

    # TODO: check or generate sort order tag
