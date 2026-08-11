from albums.tagger.types import BasicField

from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckAlbumArtistSort(BaseCheckTagPerAlbum):
    name = "album-artist-sort"
    tag = BasicField.ALBUMARTISTSORT
    tag_description = "album-artist sort order"

    # TODO: check or generate sort order tag
