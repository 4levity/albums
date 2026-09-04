from albums.checks.base_check_sort import BaseCheckSortField
from albums.tagger import BasicField


class CheckAlbumSort(BaseCheckSortField):
    name = "album-sort"
    field = BasicField.ALBUMSORT
    source_field = BasicField.ALBUM
    field_description = "album sort order"
    must_pass_checks = {"album"}
