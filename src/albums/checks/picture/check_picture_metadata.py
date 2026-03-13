import logging
import mimetypes
from os import rename
from pathlib import Path

from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...tagger.types import Picture
from ...types import Album, CheckResult, Fixer
from ..base_check import Check

logger = logging.getLogger(__name__)


class CheckPictureMetadata(Check):
    name = "picture-metadata"
    default_config = {"enabled": True}
    must_pass_checks = {"invalid-image"}

    def check(self, album: Album) -> CheckResult | None:
        if not all(AlbumTagger.supports(track.filename, Cap.PICTURES) for track in album.tracks):
            return None

        embedded_mismatches: list[int] = []
        example: str | None = None
        file_issues: list[str] = []
        for track_index, track in enumerate(album.tracks):
            issues: set[str] = set()
            for picture in track.pictures:
                load_issue = dict(picture.picture_info.load_issue)
                if picture.picture_info.load_issue and any(issue in load_issue for issue in ["format", "width", "height"]):
                    if "format" in load_issue:
                        issues.add("wrong MIME type")
                    if "width" in load_issue or "height" in load_issue:
                        issues.add("wrong dimensions")
                    if not example:
                        actual = f"{picture.picture_info.mime_type} {picture.picture_info.width}x{picture.picture_info.height}"
                        if "height" in load_issue or "width" in load_issue:
                            expect_dimensions = (
                                f" {load_issue.get('width', picture.picture_info.width)}x{load_issue.get('height', picture.picture_info.height)}"
                            )
                        else:
                            expect_dimensions = ""
                        format = load_issue.get("format", picture.picture_info.mime_type)
                        reported = f"{format if format else '(no MIME type)'}" + expect_dimensions
                        example = f"{actual} but container says {reported}"
            if issues:
                embedded_mismatches.append(track_index)
            file_issues.append(", ".join(issues))

        image_files_to_rename: list[tuple[str, str]] = []
        for file in album.picture_files:
            expect_suffix = mimetypes.guess_extension(file.picture_info.mime_type)
            path = Path(file.filename)
            if expect_suffix and str.lower(path.suffix) != str.lower(expect_suffix):
                new_filename = path.with_suffix(expect_suffix).name
                image_files_to_rename.append((file.filename, new_filename))
                file_issues.append(f"should be {expect_suffix}")
                if not example:
                    example = f"{file.filename} should be {new_filename}"
            else:
                file_issues.append("")

        if embedded_mismatches or image_files_to_rename:
            fixes: list[str] = []
            problems: list[str] = []
            if embedded_mismatches:
                problems.append(f"embedded image metadata mismatch on {len(embedded_mismatches)} tracks")
                fixes.append("re-embedding images in tracks")
            if image_files_to_rename:
                problems.append("image files with wrong extension")
                fixes.append("renaming image files")
            options = [f">> Fix by {' and '.join(fixes)}"]
            option_automatic_index = 0
            files = [escape(track.filename) for track in album.tracks] + [escape(file.filename) for file in album.picture_files]
            table = (["filename", "image metadata issues"], [[file, file_issues[ix]] for ix, file in enumerate(files)])
            return CheckResult(
                f"{' and '.join(problems)}, example {example}",
                Fixer(lambda _: self._fix(album, embedded_mismatches, image_files_to_rename), options, False, option_automatic_index, table),
            )

    def _fix(self, album: Album, mismatch_tracks: list[int], image_files_to_rename: list[tuple[str, str]]):
        for track_index in mismatch_tracks:
            track = album.tracks[track_index]
            self.ctx.console.print(f"Re-embedding pictures in {escape(track.filename)}", highlight=False)
            tagger = self.tagger.get(album.path)
            with tagger.open(track.filename) as tags:
                all_pictures = list(tags.get_pictures())
                for pic, _data in all_pictures:
                    tags.remove_picture(pic)
                for pic, image_data in all_pictures:
                    new_pic_scan = tagger.get_picture_scanner().scan(image_data)
                    new_pic = Picture(new_pic_scan, pic.type, pic.description)
                    tags.add_picture(new_pic, image_data)
        album_path = self.ctx.config.library / album.path
        for old_name, new_name in image_files_to_rename:
            self.ctx.console.print(f"Renaming {escape(old_name)} to {escape(new_name)}", highlight=False)
            rename(album_path / old_name, album_path / new_name)
        return True
