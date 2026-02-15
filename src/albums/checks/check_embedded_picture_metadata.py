import logging
from typing import List

from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from PIL.ImageFile import ImageFile
from rich.console import RenderableType
from rich.markup import escape

from ..library.picture import IMAGE_MODE_BPP, get_image
from ..types import Album, PictureType
from .base_check import Check, CheckResult, Fixer, ProblemCategory

logger = logging.getLogger(__name__)


class CheckEmbeddedPictureMetadata(Check):
    name = "embedded_picture_metadata"
    default_config = {"enabled": True}
    must_pass_checks = {"invalid_image"}

    def check(self, album: Album) -> CheckResult | None:
        mismatches: list[int] = []
        example: str | None = None
        for track_index, track in enumerate(album.tracks):
            mismatch = False
            for picture in track.pictures:
                if picture.load_issue and any(issue in picture.load_issue for issue in ["format", "width", "height"]):
                    mismatch = True
                    if not example:
                        actual = f"{picture.format} {picture.width}x{picture.height}"
                        reported = f"{picture.load_issue.get('format', picture.format)} {picture.load_issue.get('width', picture.width)}x{picture.load_issue.get('height', picture.height)}"
                        example = f"{actual} but container says {reported}"
            if mismatch:
                mismatches.append(track_index)

        if mismatches:
            if album.codec() == "FLAC":
                options = [f">> Re-embed images in {len(mismatches)} tracks"]
                option_automatic_index = 0
                tracks: List[List[RenderableType]] = [
                    [escape(track.filename), "**yes**" if ix in mismatches else ""] for ix, track in enumerate(album.tracks)
                ]
                table = (["filename", "image metadata issues"], tracks)
                fixer = Fixer(lambda _: self._fix(album, mismatches), options, False, option_automatic_index, table)
            else:
                # TODO implement for MP3 and Ogg Vorbis too, see also invalid_image
                fixer = None

            return CheckResult(
                ProblemCategory.PICTURES,
                f"embedded image metadata mismatch on {len(mismatches)} tracks, example {example}",
                fixer,
            )

    def _fix(self, album: Album, mismatch_tracks: list[int]):
        for track_index in mismatch_tracks:
            track = album.tracks[track_index]
            file = self.ctx.config.library / album.path / track.filename
            if track.stream and track.stream.codec == "FLAC":
                self.ctx.console.print(f"re-embedding pictures in {escape(str(file))}", highlight=False)
                flac = FLAC(file)

                def fix(flac_pictures: list[FlacPicture]):
                    pics: list[tuple[PictureType, bytes, ImageFile, str]] = []
                    for ix, pic in enumerate(flac_pictures):
                        image_info = get_image(pic.data)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
                        if isinstance(image_info, str):
                            logger.error(f"failed to load FLAC picture #{ix} because: {image_info}")
                            return False  # don't do anything to this file
                        else:
                            (image, mime) = image_info
                            pics.append((PictureType(pic.type), pic.data, image, mime))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

                    flac.clear_pictures()
                    for picture_type, image_data, image, mime in pics:
                        flac_pic = FlacPicture()
                        flac_pic.data = image_data
                        flac_pic.type = picture_type
                        flac_pic.mime = mime
                        flac_pic.width = image.width
                        flac_pic.height = image.height
                        flac_pic.depth = 24 if mime == "image/jpeg" else IMAGE_MODE_BPP.get(image.mode, 0)
                        flac.add_picture(flac_pic)  # pyright: ignore[reportUnknownMemberType]
                    return True

                if fix(flac.pictures):  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
                    flac.save()  # pyright: ignore[reportUnknownMemberType]
                else:
                    logger.error(f"changes NOT saved to file {str(file)}")
            else:
                raise ValueError(f"unexpected metadata mismatch report on non-FLAC file {str(file)}")
        return True
