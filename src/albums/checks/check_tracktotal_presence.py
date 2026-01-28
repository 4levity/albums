from albums.checks.base_check_total_tag import AbstractCheckTotalTag


class CheckTrackTotalPresence(AbstractCheckTotalTag):
    name = "tracktotal_presence"
    tag_name = "tracktotal"
