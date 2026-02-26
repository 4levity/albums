import logging

from rich.markup import escape

from ...tagger.types import AlbumPicture
from ...types import Album, CheckResult, Fixer, ProblemCategory
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
            if self.tagger.get(album.path).supports(*(album.tracks[ix].filename for ix in mismatches)):
                options = [f">> Re-embed images in {len(mismatches)} tracks"]
                option_automatic_index = 0
                tracks = [[escape(track.filename), "yes" if ix in mismatches else ""] for ix, track in enumerate(album.tracks)]
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
        for track_index in mismatch_tracks:
            track = album.tracks[track_index]
            self.ctx.console.print(f"re-embedding pictures in {escape(track.filename)}", highlight=False)
            tagger = self.tagger.get(album.path)
            with tagger.open(track.filename) as tags:
                all_pictures = list(tags.get_pictures())
                for pic, _data in all_pictures:
                    tags.remove_picture(pic)
                for pic, image_data in all_pictures:
                    new_pic_scan = tagger.get_picture_scanner().scan(image_data)
                    new_pic = AlbumPicture(new_pic_scan.picture_info, pic.picture_type, pic.description, new_pic_scan.load_issue)
                    tags.add_picture(new_pic, image_data)
        return True
