import logging
from pathlib import Path
from typing import List

from mutagen.flac import FLAC
from mutagen.flac import Picture as FlacPicture
from mutagen.mp3 import MP3
from PIL.Image import Image
from rich.console import RenderableType
from rich.markup import escape

from ...library.metadata import IMAGE_MODE_BPP, add_id3_pictures, get_id3_pictures, get_image
from ...types import Album, CheckResult, Fixer, Picture, PictureType, ProblemCategory
from ..base_check import Check

logger = logging.getLogger(__name__)


class CheckEmbeddedPictureMetadata(Check):
    name = "embedded-picture-metadata"
    default_config = {"enabled": True}
    must_pass_checks = {"invalid-image"}

    def check(self, album: Album) -> CheckResult | None:
        # TODO: this check or a separate one should also report if image files have the wrong extension
        mismatches: list[int] = []
        example: str | None = None
        for track_index, track in enumerate(album.tracks):
            mismatch = False
            for picture in track.pictures:
                if picture.load_issue and any(issue in picture.load_issue for issue in ["format", "width", "height"]):
                    mismatch = True
                    if not example:
                        actual = f"{picture.format} {picture.width}x{picture.height}"
                        if "height" in picture.load_issue or "width" in picture.load_issue:
                            expect_dimensions = (
                                f" {picture.load_issue.get('width', picture.width)}x{picture.load_issue.get('height', picture.height)}"
                            )
                        else:
                            expect_dimensions = ""
                        format = picture.load_issue.get("format", picture.format)
                        reported = f"{format if format else '(no MIME type)'}" + expect_dimensions
                        example = f"{actual} but container says {reported}"
            if mismatch:
                mismatches.append(track_index)

        if mismatches:
            if album.codec() in {"FLAC", "MP3"}:
                options = [f">> Re-embed images in {len(mismatches)} tracks"]
                option_automatic_index = 0
                tracks: List[List[RenderableType]] = [
                    [escape(track.filename), "yes" if ix in mismatches else ""] for ix, track in enumerate(album.tracks)
                ]
                table = (["filename", "image metadata issues"], tracks)
                fixer = Fixer(lambda _: self._fix(album, mismatches), options, False, option_automatic_index, table)
            else:
                # TODO implement for Ogg Vorbis too, see also invalid-image
                fixer = None

            return CheckResult(
                ProblemCategory.PICTURES,
                f"embedded image metadata mismatch on {len(mismatches)} tracks, example {example}",
                fixer,
            )

    def _fix(self, album: Album, mismatch_tracks: list[int]):
        changed = False
        for track_index in mismatch_tracks:
            track = album.tracks[track_index]
            file = self.ctx.config.library / album.path / track.filename
            if track.stream and track.stream.codec == "FLAC":
                self.ctx.console.print(f"re-embedding pictures in {escape(str(file))}", highlight=False)
                changed |= self._re_embed_flac(file)
            elif track.stream and track.stream.codec == "MP3":
                self.ctx.console.print(f"re-embedding pictures in {escape(str(file))}", highlight=False)
                changed |= self._re_embed_mp3(file)
            else:
                raise ValueError(f"unexpected file type {str(file)}")
        return changed

    def _re_embed_flac(self, file: Path):
        flac = FLAC(file)
        pics: list[tuple[PictureType, bytes, Image, str]] = []
        flac_pictures: list[FlacPicture] = flac.pictures  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
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

        flac.save()  # pyright: ignore[reportUnknownMemberType]
        return True

    def _re_embed_mp3(self, file: Path):
        mp3 = MP3(file)
        pics: list[tuple[Picture, bytes]] = []
        for ix, (pic, image_data) in enumerate(get_id3_pictures(mp3.tags, {})):  # pyright: ignore[reportArgumentType, reportUnknownMemberType]
            image_info = get_image(image_data)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            if isinstance(image_info, str):
                logger.error(f"failed to load ID3 picture #{ix} because: {image_info}")
                return False  # don't do anything to this file
            else:
                (_, mime) = image_info
                pic.format = mime
                pics.append((pic, image_data))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

        mp3.tags.delall("APIC")  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType]
        add_id3_pictures(mp3.tags, pics)  # pyright: ignore[reportArgumentType, reportUnknownMemberType]
        mp3.save()  # pyright: ignore[reportUnknownMemberType]
        return True
