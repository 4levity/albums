import logging
from pathlib import Path

from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from rich.markup import escape

from ..library.picture import IMAGE_MODE_BPP, get_image
from ..types import Album, PictureType
from .base_check import Check, CheckResult, Fixer, ProblemCategory

logger = logging.getLogger(__name__)


class CheckFlacPictureMetadata(Check):
    name = "flac_picture_metadata"
    default_config = {"enabled": True}

    def check(self, album: Album) -> CheckResult | None:
        mismatches: list[int] = []
        example: str | None = None
        for track_index, track in enumerate(album.tracks):
            mismatch = False
            for picture in track.pictures:
                if picture.mismatch:
                    mismatch = True
                    if not example:
                        actual = f"{picture.format} {picture.width}x{picture.height}"
                        reported = f"{picture.mismatch.get('format', picture.format)} {picture.mismatch.get('width', picture.width)}x{picture.mismatch.get('height', picture.height)}"
                        example = f"{actual} but container says {reported}"
            if mismatch:
                mismatches.append(track_index)

        if mismatches:
            options = [f">> Re-embed images in {len(mismatches)} tracks"]
            option_automatic_index = 0
            tracks = [[escape(track.filename), "**yes**" if ix in mismatches else ""] for ix, track in enumerate(album.tracks)]
            table = (["filename", "image metadata issues"], tracks)
            return CheckResult(
                ProblemCategory.PICTURES,
                f"embedded image metadata mismatch on {len(mismatches)} tracks, example {example}",
                Fixer(lambda _: self._fix(album, mismatches), options, False, option_automatic_index, table),
            )

    def _fix(self, album: Album, mismatch_tracks: list[int]):
        for track_index in mismatch_tracks:
            track = album.tracks[track_index]
            file = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / track.filename
            if track.stream and track.stream.codec == "FLAC":
                self.ctx.console.print(f"re-embedding pictures in {str(file)}")
                flac = FLAC(file)

                def fix(flac_pictures: list[FlacPicture]):
                    pics: list[tuple[PictureType, bytes]] = []
                    for pic in flac_pictures:
                        pics.append((PictureType(pic.type), pic.data))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    flac.clear_pictures()
                    for picture_type, image_data in pics:
                        (image, mime) = get_image(image_data)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
                        flac_pic = FlacPicture()
                        flac_pic.data = image_data
                        flac_pic.type = picture_type
                        flac_pic.mime = mime
                        flac_pic.width = image.width
                        flac_pic.height = image.height
                        flac_pic.depth = 24 if mime == "image/jpeg" else IMAGE_MODE_BPP.get(image.mode, 0)
                        flac.add_picture(flac_pic)  # pyright: ignore[reportUnknownMemberType]

                fix(flac.pictures)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
                flac.save()  # pyright: ignore[reportUnknownMemberType]
            else:
                raise ValueError(f"unexpected metadata mismatch report on non-FLAC file {str(file)}")
        return True
