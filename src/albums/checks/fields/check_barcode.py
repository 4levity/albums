from albums.checks.base_check_field_per_album import BaseCheckFieldPerAlbum
from albums.tagger.types import BasicField


class CheckBarcodeField(BaseCheckFieldPerAlbum):
    name = "barcode"
    field = BasicField.BARCODE
