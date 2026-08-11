from albums.tagger.types import BasicField

from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckBarcodeTag(BaseCheckTagPerAlbum):
    name = "barcode-tag"
    tag = BasicField.BARCODE
