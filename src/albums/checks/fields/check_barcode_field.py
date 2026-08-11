from albums.tagger.types import BasicField

from ..base_check_field_per_album import BaseCheckFieldPerAlbum


class CheckBarcodeField(BaseCheckFieldPerAlbum):
    name = "barcode-field"
    field = BasicField.BARCODE
