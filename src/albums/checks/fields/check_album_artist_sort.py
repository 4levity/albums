from albums.checks.base_check_sort import BaseCheckSortField
from albums.tagger import BasicField


class CheckAlbumArtistSort(BaseCheckSortField):
    name = "album-artist-sort"
    field = BasicField.ALBUMARTISTSORT
    source_field = BasicField.ALBUMARTIST
    field_description = "album-artist sort order"
    must_pass_checks = {"album-artist"}
