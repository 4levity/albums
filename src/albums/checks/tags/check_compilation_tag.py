from ...types import BasicTag
from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckCompilationTag(BaseCheckTagPerAlbum):
    name = "compilation-tag"
    tag = BasicTag.COMPILATION

    # TODO: report if compilation flag set but not a compilation + configuration option to control compilation flag
