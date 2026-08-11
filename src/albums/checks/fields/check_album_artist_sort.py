from albums.tagger.types import BasicField

from ..base_check_field_per_album import BaseCheckFieldPerAlbum


class CheckAlbumArtistSort(BaseCheckFieldPerAlbum):
    name = "album-artist-sort"
    field = BasicField.ALBUMARTISTSORT
    field_description = "album-artist sort order"

    # TODO: check or generate sort order tag
