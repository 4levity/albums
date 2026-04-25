from ...types import BasicTag
from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckBarcodeTag(BaseCheckTagPerAlbum):
    name = "barcode-tag"
    tag = BasicTag.BARCODE
