import io
import logging
import mimetypes
from typing import Any, List, Tuple

from PIL.Image import Image, Resampling
from rich.console import RenderableType

from ..database.operations import update_picture_files
from ..interactive.image_table import render_image_table
from ..library.metadata import add_embedded_image, read_image, replace_embedded_image
from ..types import Album, CheckResult, Fixer, Picture, PictureType, ProblemCategory
from .base_check import Check
from .helpers import FRONT_COVER_FILENAME

logger = logging.getLogger(__name__)


class CheckCoverEmbedded(Check):
    name = "cover_embedded"
    default_config = {
        "enabled": True,
        "max_height_width": 1000,
        "require_mime_type": "",
        "create_mime_type": "image/jpeg",
        "create_max_height_width": 600,
        "create_jpeg_quality": 80,
    }
    must_pass_checks = {"duplicate_image"}  # cover_selection with unique=True is recommended but not required

    def init(self, check_config: dict[str, Any]):
        defaults = CheckCoverEmbedded.default_config
        self.max_height_width = int(check_config.get("max_height_width", defaults["max_height_width"]))
        self.require_mime_type = str(check_config.get("require_mime_type", defaults["require_mime_type"]))
        if self.require_mime_type not in {"", "image/jpeg", "image/png"}:
            raise ValueError("cover_embedded.require_mime_type must be either blank, image/jpeg or image/png")
        self.create_mime_type = str(check_config.get("create_mime_type", defaults["create_mime_type"]))
        if self.create_mime_type not in {"image/jpeg", "image/png"}:
            raise ValueError("cover_embedded.create_mime_type must be either image/jpeg or image/png")
        self.create_max_height_width = int(check_config.get("create_max_height_width", defaults["create_max_height_width"]))
        self.create_jpeg_quality = int(check_config.get("create_jpeg_quality", defaults["create_jpeg_quality"]))
        if self.create_jpeg_quality < 1 or self.create_jpeg_quality > 95:
            raise ValueError("cover_embedded.create_jpeg_quality must be between 1 and 95")

    def check(self, album: Album) -> CheckResult | None:
        cover_source = next(((filename, pic) for filename, pic in album.picture_files.items() if pic.cover_source), None)
        # depends on duplicate_image, which ensures there is only one COVER_FRONT embedded per track
        track_covers = [next(((t.filename, p) for p in t.pictures if p.picture_type == PictureType.COVER_FRONT), None) for t in album.tracks]
        unique_track_covers = set(cover_spec[1] for cover_spec in track_covers if cover_spec)
        missing = sum(0 if c else 1 for c in track_covers)

        if cover_source:
            (cover_source_filename, cover_source_picture) = cover_source
            (expect_w, expect_h) = self._embedded_image_spec(cover_source_picture)
            all_as_expected = all(c and (c[1].width, c[1].height, c[1].format) == (expect_w, expect_h, self.create_mime_type) for c in track_covers)
            if not all_as_expected:
                not_expected_size = sum(0 if not c or c and (c[1].width, c[1].height) == (expect_w, expect_h) else 1 for c in track_covers)
                not_expected_format = sum(0 if not c or c and c[1].format == self.create_mime_type else 1 for c in track_covers)
                problem_summary = f"{not_expected_size} tracks with unexpected dimensions and {not_expected_format} tracks with unexpected MIME type"
                if len(unique_track_covers) > 1:
                    # TODO we could offer a non-automatic fix if user wants to overwrite non-unique covers
                    return CheckResult(
                        ProblemCategory.PICTURES,
                        f"{problem_summary}, but more than one unique embedded cover image, and images are not {expect_w} x {expect_h} {self.create_mime_type} as expected",
                    )

                track_cover = next(filter(None, track_covers), None)
                headers = [f"Front Cover Source {cover_source_filename}"]
                pictures = [cover_source_picture]
                pic_sources: dict[Picture, list[tuple[str, bool, int]]] = {cover_source_picture: [(cover_source_filename, False, 0)]}
                if track_cover:
                    (_, track_cover_pic) = track_cover
                    headers.append("Current Embedded Cover")
                    pictures.append(track_cover_pic)
                    for tc in track_covers:
                        if tc:
                            (filename, pic) = tc
                            src = (filename, True, pic.embed_ix)
                            if track_cover_pic in pic_sources:
                                pic_sources[track_cover_pic].append(src)
                            else:
                                pic_sources[track_cover_pic] = [src]
                headers.append("Preview New Embedded Cover")
                options = [">> Embed new cover art in all tracks"]
                option_automatic_index = 0
                return CheckResult(
                    ProblemCategory.PICTURES,
                    f"{problem_summary}, can re-embed from front cover source",
                    Fixer(
                        lambda _: self._fix_embed_cover_in_all_tracks(album, cover_source_filename, cover_source_picture, False),
                        options,
                        False,
                        option_automatic_index,
                        (headers, lambda: self._get_table_rows(album, pictures, pic_sources, cover_source_picture, cover_source_filename, False)),
                    ),
                )
            # else: all done
            return None

        # else: there is no cover_source marked
        def good_enough(cover: Picture):
            return (
                (cover.format == self.require_mime_type or not self.require_mime_type)
                and cover.width < self.max_height_width
                and cover.height < self.max_height_width
            )

        all_good_enough = all(c and good_enough(c[1]) for c in track_covers)
        if not all_good_enough:
            not_good_enough = sum(0 if not c or c and good_enough(c[1]) else 1 for c in track_covers)
            problem_summary = f"{missing} tracks with no cover and {not_good_enough} tracks with out of spec covers"
            cover_files = [(filename, pic) for filename, pic in album.picture_files.items() if pic.picture_type == PictureType.COVER_FRONT]

            unique_covers = unique_track_covers.union(pic for _, pic in cover_files)
            if len(unique_covers) > 1:
                return CheckResult(
                    ProblemCategory.PICTURES,
                    f'{problem_summary}, but there are {len(unique_covers)} unique front covers and no cover_source (enable cover_selection "unique" for fixes)',
                )
            # else
            if len(unique_covers) == 1:
                # there is one unique cover. if we just mark it as cover_source, embedded images can be automatically fixed on recheck
                cover = next(iter(unique_covers))
                if cover_files:  # mark existing file as cover source
                    (filename, _) = cover_files[0]
                    options = [f">> Mark as front cover source: {filename}"]
                    option_automatic_index = 0
                    table = ([filename], lambda: render_image_table(self.ctx, album, [cover], {cover: [(filename, False, 0)]}))
                    return CheckResult(
                        ProblemCategory.PICTURES,
                        f"{problem_summary}, but the file {filename} can be marked as cover_source (afterwards, a recheck can fix tracks)",
                        Fixer(lambda _: self._fix_mark_cover_source(album, filename), options, False, option_automatic_index, table),
                    )
                # else
                # create a cover.jpg/.png file and mark it as cover source
                (filename, cover) = next(filter(None, track_covers))
                options = [">> Extract embedded cover and mark as front cover source"]
                option_automatic_index = 0
                table = (["Embedded Cover"], lambda: render_image_table(self.ctx, album, [cover], {cover: [(filename, True, cover.embed_ix)]}))
                return CheckResult(
                    ProblemCategory.PICTURES,
                    f"{problem_summary}, but the cover can be extracted and marked as cover_source (afterwards, a recheck can fix tracks)",
                    Fixer(lambda _: self._fix_extract_cover_source(album, filename, cover), options, False, option_automatic_index, table),
                )
            # else: no covers available, cover not required by earlier checks
        # else: no cover_source + all tracks have "good enough" embedded cover art
        return None

    def _embedded_image_spec(self, cover_source: Picture):
        dim = max(cover_source.width, cover_source.height)
        scale = 1 if dim <= self.create_max_height_width else (self.create_max_height_width / dim)
        return (round(cover_source.width * scale), round(cover_source.height * scale))

    def _make_embedded(self, album: Album, source_filename: str, source_picture: Picture, source_embedded: bool) -> Tuple[Image, bytes]:
        path = self.ctx.config.library / album.path / source_filename
        source = read_image(path, source_embedded, source_picture.embed_ix)
        if not source:
            raise RuntimeError(f"failed to read cover image source file {str(path)}")
        (source_image, _) = source
        source_image.load()  # fail here if not loadable
        (new_w, new_h) = self._embedded_image_spec(source_picture)
        new_format = self.create_mime_type
        if source_image.width == new_w and source_image.height == new_h and source_picture.format == new_format:
            return source
        source_image.thumbnail((self.create_max_height_width, self.create_max_height_width), Resampling.LANCZOS)
        buffer = io.BytesIO()
        format = {"image/jpeg": "JPEG", "image/png": "PNG"}[self.create_mime_type]
        source_image.save(buffer, format, quality=self.create_jpeg_quality)
        return (source_image, buffer.getvalue())

    def _fix_embed_cover_in_all_tracks(self, album: Album, source_filename: str, source_picture: Picture, source_embedded: bool):
        (image, image_data) = self._make_embedded(album, source_filename, source_picture, source_embedded)
        new_cover = Picture(
            PictureType.COVER_FRONT, self.create_mime_type, image.width, image.height, len(image_data), b""
        )  # hash/etc fixed on rescan
        for track in album.tracks:
            current_cover = next(filter(lambda pic: pic.picture_type == PictureType.COVER_FRONT, track.pictures), None)
            path = self.ctx.config.library / album.path / track.filename
            if not track.stream:
                raise ValueError(f"missing stream metadata for track {track.filename}")
            if current_cover:
                self.ctx.console.print(f"Replacing front cover image in {track.filename}")
                replace_embedded_image(path, track.stream.codec, current_cover, new_cover, image, image_data)
            else:
                self.ctx.console.print(f"Adding front cover image to {track.filename}")
                add_embedded_image(path, track.stream.codec, new_cover, image, image_data)
        return True

    def _fix_mark_cover_source(self, album: Album, filename: str):
        if not self.ctx.db or not album.album_id:
            raise ValueError("marking cover source requires database and album_id")
        self.ctx.console.print(f"Mark as front cover source: {filename}")
        album.picture_files[filename].cover_source = True
        update_picture_files(self.ctx.db, album.album_id, album.picture_files)
        return True

    def _fix_extract_cover_source(self, album: Album, filename: str, cover: Picture):
        if not self.ctx.db or not album.album_id:
            raise ValueError("extracting cover source requires database and album_id")
        source_path = self.ctx.config.library / album.path / filename
        source = read_image(source_path, True, cover.embed_ix)
        if not source:
            raise RuntimeError(f"failed to extract cover image source from {str(source_path)}")
        (source_image, image_data) = source
        source_image.load()  # fail here if not loadable

        suffix = mimetypes.guess_extension(cover.format)
        new_filename = f"{FRONT_COVER_FILENAME}{suffix}"
        self.ctx.console.print(f"Extract to cover source: {new_filename}")
        with open(self.ctx.config.library / album.path / new_filename, "wb") as f:
            f.write(image_data)
        # create a record of the new image so it can be marked cover_source (details will be filled in when album is rescanned)
        album.picture_files[new_filename] = Picture(PictureType.COVER_FRONT, cover.format, 0, 0, 0, b"", "", None, 0)
        return self._fix_mark_cover_source(album, new_filename)

    def _get_table_rows(
        self,
        album: Album,
        some_pictures: list[Picture],
        pic_sources: dict[Picture, list[tuple[str, bool, int]]],
        source_picture: Picture,
        source_filename: str,
        source_embedded: bool,
    ) -> List[List[RenderableType]]:
        (preview_image, preview_data) = self._make_embedded(album, source_filename, source_picture, source_embedded)
        preview_pic = Picture(PictureType.COVER_FRONT, self.create_mime_type, preview_image.width, preview_image.height, len(preview_data), b"")
        pictures = some_pictures + [(preview_pic, preview_image, preview_data)]
        return render_image_table(self.ctx, album, pictures, pic_sources)
