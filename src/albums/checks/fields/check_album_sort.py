from albums.checks.base_check_field_per_album import BaseCheckFieldPerAlbum
from albums.tagger import BasicField


class CheckAlbumSort(BaseCheckFieldPerAlbum):
    name = "album-sort"
    field = BasicField.ALBUMSORT
    field_description = "album sort order"

    # TODO: check or generate sort order field
