from albums.checks.base_check_sort import BaseCheckSortField
from albums.tagger import BasicField


class CheckArtistSort(BaseCheckSortField):
    name = "artist-sort"
    field = BasicField.ARTISTSORT
    source_field = BasicField.ARTIST
    field_description = "artist sort order"
    must_pass_checks = {"artist"}
