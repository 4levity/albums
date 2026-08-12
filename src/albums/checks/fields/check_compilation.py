from albums.tagger.types import BasicField

from ..base_check_field_per_album import BaseCheckFieldPerAlbum


class CheckCompilationField(BaseCheckFieldPerAlbum):
    name = "compilation"
    field = BasicField.COMPILATION

    # TODO: report if compilation flag set but not a compilation + configuration option to control compilation flag
