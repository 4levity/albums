from albums.tagger.types import BasicField

from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckCompilationTag(BaseCheckTagPerAlbum):
    name = "compilation-tag"
    tag = BasicField.COMPILATION

    # TODO: report if compilation flag set but not a compilation + configuration option to control compilation flag
