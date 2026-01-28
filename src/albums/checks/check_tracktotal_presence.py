from albums.checks.base_check_total_tag import AbstractCheckTotalTag


class CheckTrackTotalPresence(AbstractCheckTotalTag):
    name = "tracktotal_presence"
    total_tag_name = "tracktotal"
    corresponding_index_tag = "tracknumber"
