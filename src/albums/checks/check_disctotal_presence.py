from albums.checks.base_check_total_tag import AbstractCheckTotalTag


class CheckDiscTotalPresence(AbstractCheckTotalTag):
    name = "disctotal_presence"
    total_tag_name = "disctotal"
    corresponding_index_tag = "discnumber"
