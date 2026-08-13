from albums.checks.base_check_field_per_album import BaseCheckFieldPerAlbum
from albums.tagger import BasicField


class CheckCompilationField(BaseCheckFieldPerAlbum):
    name = "compilation"
    field = BasicField.COMPILATION

    # TODO: report if compilation flag set but not a compilation + configuration option to control compilation flag
