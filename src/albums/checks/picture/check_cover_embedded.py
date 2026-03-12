import io
import logging
import mimetypes
from typing import Any, Sequence, Tuple

from PIL import Image
from rich.console import RenderableType
from rich.markup import escape

from albums.tagger.folder import Cap

from ...database.models import AlbumEntity, PictureFileEntity
from ...interactive.image_table import render_image_table
from ...library.folder import read_binary_file
from ...picture.format import MIME_PILLOW_FORMAT
from ...picture.info import PictureInfo
from ...tagger.types import Picture, PictureType
from ...types import CheckResult, Fixer
from ..base_check import Check
from ..helpers import FRONT_COVER_FILENAME

logger = logging.getLogger(__name__)


class CheckCoverEmbedded(Check):
    name = "cover-embedded"
    default_config = {
        "enabled": True,
        "max_height_width": 1000,
        "require_mime_type": "",
        "create_mime_type": "image/jpeg",
        "create_max_height_width": 600,
        "create_jpeg_quality": 80,
    }
    must_pass_checks = {"conflicting-embedded"}  # cover-unique is recommended but not required

    def init(self, check_config: dict[str, Any]):
        defaults = CheckCoverEmbedded.default_config
        self.max_height_width = int(check_config.get("max_height_width", defaults["max_height_width"]))
        self.require_mime_type = str(check_config.get("require_mime_type", defaults["require_mime_type"]))
        if self.require_mime_type not in {"", "image/jpeg", "image/png"}:
            raise ValueError("cover-embedded.require_mime_type must be either blank, image/jpeg or image/png")
        self.create_mime_type = str(check_config.get("create_mime_type", defaults["create_mime_type"]))
        if self.create_mime_type not in {"image/jpeg", "image/png"}:
            raise ValueError("cover-embedded.create_mime_type must be either image/jpeg or image/png")
        self.create_max_height_width = int(check_config.get("create_max_height_width", defaults["create_max_height_width"]))
        self.create_jpeg_quality = int(check_config.get("create_jpeg_quality", defaults["create_jpeg_quality"]))
        if self.create_jpeg_quality < 1 or self.create_jpeg_quality > 95:
            raise ValueError("cover-embedded.create_jpeg_quality must be between 1 and 95")

    def check(self, album: AlbumEntity) -> CheckResult | None:
        cover_source = next((pic for pic in album.picture_files if pic.cover_source), None)
        # depends on conflicting-embedded, which ensures there is only one COVER_FRONT embedded per track
        tagger = self.tagger.get(album.path)
        track_covers = [
            next(((t.filename, p) for p in t.pictures if p.picture_type == PictureType.COVER_FRONT), None)
            for t in album.tracks
            if tagger.supports(t.filename, Cap.PICTURES)
        ]
        unique_track_covers = set(cover_spec[1] for cover_spec in track_covers if cover_spec)
        missing = sum(0 if c else 1 for c in track_covers)
        unsupported = sum(0 if tagger.supports(t.filename) else 1 for t in album.tracks)

        if cover_source:
            (expect_w, expect_h) = self._embedded_image_spec(cover_source.picture_info)
            all_as_expected = all(
                c and (c[1].picture_info.width, c[1].picture_info.height, c[1].picture_info.mime_type) == (expect_w, expect_h, self.create_mime_type)
                for c in track_covers
            )
            if not all_as_expected:
                not_expected_size = sum(
                    0 if not c or c and (c[1].picture_info.width, c[1].picture_info.height) == (expect_w, expect_h) else 1 for c in track_covers
                )
                not_expected_format = sum(0 if not c or c and c[1].picture_info.mime_type == self.create_mime_type else 1 for c in track_covers)
                problems: list[str] = []
                if unsupported:
                    problems.append(f"{unsupported} tracks where albums doesn't support embedded images")
                if missing:
                    problems.append(f"{missing} with no cover")
                if not_expected_size:
                    problems.append(f"{not_expected_size} with wrong dimensions")
                if not_expected_format:
                    problems.append(f"{not_expected_format} with wrong MIME type")
                problem_summary = ", ".join(problems)
                if len(unique_track_covers) > 1:
                    # TODO we could offer a non-automatic fix if user wants to overwrite non-unique covers
                    return CheckResult(
                        f"{problem_summary}, but more than one unique embedded cover image, and images are not {expect_w} x {expect_h} {self.create_mime_type} as expected",
                    )

                track_cover = next(filter(None, track_covers), None)
                headers = [f"Front Cover Source {cover_source.filename}"]
                cover_source_picture = Picture(cover_source.picture_info, PictureType.COVER_FRONT, "")
                pictures = [cover_source_picture]
                pic_sources: dict[Picture, list[str]] = {cover_source_picture: [cover_source.filename]}
                if track_cover:
                    (_, track_cover_pic) = track_cover
                    headers.append("Current Embedded Cover")
                    pictures.append(track_cover_pic.to_picture())
                    for tc in track_covers:
                        if tc:
                            (filename, _) = tc
                            src = filename
                            if track_cover_pic.to_picture() in pic_sources:
                                pic_sources[track_cover_pic.to_picture()].append(src)
                            else:
                                pic_sources[track_cover_pic.to_picture()] = [src]
                headers.append("Preview New Embedded Cover")
                options = [">> Embed new cover art in all tracks"]
                option_automatic_index = 0
                return CheckResult(
                    f"{problem_summary}, can re-embed from front cover source",
                    Fixer(
                        lambda _: self._fix_embed_cover_in_all_tracks(album, cover_source.filename, cover_source_picture),
                        options,
                        False,
                        option_automatic_index,
                        (
                            headers,
                            lambda: self._get_table_rows(album, pictures, pic_sources, cover_source_picture, cover_source.filename),
                        ),
                    ),
                )
            # else: all done
            return None

        # else: there is no cover_source marked
        def good_enough(cover: Picture):
            return (
                (cover.picture_info.mime_type == self.require_mime_type or not self.require_mime_type)
                and cover.picture_info.width < self.max_height_width
                and cover.picture_info.height < self.max_height_width
            )

        all_good_enough = all(c and good_enough(c[1].to_picture()) for c in track_covers)
        if not all_good_enough:
            not_good_enough = sum(0 if not c or c and good_enough(c[1].to_picture()) else 1 for c in track_covers)
            problem_summary = f"{missing} tracks with no cover and {not_good_enough} tracks with out of spec covers"
            cover_files = [file for file in album.picture_files if PictureType.from_filename(file.filename) == PictureType.COVER_FRONT]

            unique_covers = unique_track_covers.union(Picture(file.picture_info, PictureType.COVER_FRONT, "") for file in cover_files)
            if len(unique_covers) > 1:
                return CheckResult(
                    f"{problem_summary}, but there are {len(unique_covers)} unique front covers and no cover_source (enable cover-unique for fixes)",
                )
            # else
            if len(unique_covers) == 1:
                # there is one unique cover. if we just mark it as cover_source, embedded images can be automatically fixed on recheck
                cover = next(iter(unique_covers))
                if cover_files:  # mark existing file as cover source
                    filename = cover_files[0].filename
                    options = [f">> Mark as front cover source: {filename}"]
                    option_automatic_index = 0
                    table = ([filename], lambda: render_image_table(self.ctx, self.tagger.get(album.path), [cover], {cover: [filename]}))
                    return CheckResult(
                        f"{problem_summary}, but the file {filename} can be marked as cover_source (afterwards, a recheck can fix tracks)",
                        Fixer(lambda _: self._fix_mark_cover_source(album, filename), options, False, option_automatic_index, table),
                    )
                # else
                # create a cover.jpg/.png file and mark it as cover source
                (filename, cover) = next(filter(None, track_covers))
                options = [">> Extract embedded cover and mark as front cover source"]
                option_automatic_index = 0
                table = (
                    ["Embedded Cover"],
                    lambda: render_image_table(self.ctx, self.tagger.get(album.path), [cover], {cover: [filename]}),
                )
                return CheckResult(
                    f"{problem_summary}, but the cover can be extracted and marked as cover_source (afterwards, a recheck can fix tracks)",
                    Fixer(lambda _: self._fix_extract_cover_source(album, filename, cover), options, False, option_automatic_index, table),
                )
            # else: no covers available, cover not required by earlier checks
        # else: no cover_source + all tracks have "good enough" embedded cover art
        return None

    def _embedded_image_spec(self, cover_source: PictureInfo):
        dim = max(cover_source.width, cover_source.height)
        scale = 1 if dim <= self.create_max_height_width else (self.create_max_height_width / dim)
        return (round(cover_source.width * scale), round(cover_source.height * scale))

    def _make_embedded(self, album: AlbumEntity, source_filename: str, source_picture: Picture) -> Tuple[Image.Image, bytes]:
        path = self.ctx.config.library / album.path / source_filename
        image_data = read_binary_file(path)

        source_image = Image.open(io.BytesIO(image_data))
        source_image.load()  # fail here if not loadable
        (new_w, new_h) = self._embedded_image_spec(source_picture.picture_info)
        new_format = self.create_mime_type
        if source_image.width == new_w and source_image.height == new_h and source_picture.picture_info.mime_type == new_format:
            return (source_image, image_data)
        if source_image.mode not in {"RGB", "L"}:
            source_image = source_image.convert("RGB")
        source_image.thumbnail((self.create_max_height_width, self.create_max_height_width), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        format = MIME_PILLOW_FORMAT[self.create_mime_type]
        source_image.save(buffer, format, quality=self.create_jpeg_quality)
        return (source_image, buffer.getvalue())

    def _fix_embed_cover_in_all_tracks(self, album: AlbumEntity, source_filename: str, source_picture: Picture):
        (image, image_data) = self._make_embedded(album, source_filename, source_picture)
        new_info = PictureInfo(self.create_mime_type, image.width, image.height, 24, len(image_data), b"")  # hash fixed on rescan
        new_cover = Picture(new_info, PictureType.COVER_FRONT, "")
        tagger = self.tagger.get(album.path)
        for track in album.tracks:
            if tagger.supports(track.filename, Cap.PICTURES):
                with tagger.open(track.filename) as tags:
                    current_cover = next((pic for pic, _data in tags.get_pictures() if pic.type == PictureType.COVER_FRONT), None)
                    if current_cover:
                        self.ctx.console.print(f"Replacing front cover image in {escape(track.filename)}")
                        tags.remove_picture(current_cover)
                    else:
                        self.ctx.console.print(f"Adding front cover image to {escape(track.filename)}")
                    tags.add_picture(new_cover, image_data)
            else:
                self.ctx.console.print(f"Skipping unsupported file {escape(track.filename)}")
        return True

    def _fix_mark_cover_source(self, album: AlbumEntity, filename: str):
        if not self.ctx.db or not album.album_id:
            raise ValueError("marking cover source requires database and album_id")
        self.ctx.console.print(f"Mark as front cover source: {escape(filename)}")
        file = next(file for file in album.picture_files if file.filename == filename)
        file.cover_source = True
        return True

    def _fix_extract_cover_source(self, album: AlbumEntity, filename: str, cover: Picture):
        if not self.ctx.db or not album.album_id:
            raise ValueError("extracting cover source requires database and album_id")

        with self.tagger.get(album.path).open(filename) as tags:
            image_data = tags.get_image_data(cover)
        source_image = Image.open(io.BytesIO(image_data))
        source_image.load()  # fail here if not loadable

        suffix = mimetypes.guess_extension(cover.picture_info.mime_type)
        new_filename = f"{FRONT_COVER_FILENAME}{suffix}"
        self.ctx.console.print(f"Extract to cover source: {escape(new_filename)}")
        path = self.ctx.config.library / album.path / new_filename
        if path.exists():
            raise RuntimeError(f"unexpected: path exists {str(path)}")  # shouldn't happen because this fix is offered when there are no cover files
        with open(path, "wb") as f:
            f.write(image_data)
        # create a record of the new image so it can be marked cover_source (details will be filled in when album is rescanned)
        album.picture_files.append(
            PictureFileEntity(filename=new_filename, picture_info=PictureInfo(cover.picture_info.mime_type, 0, 0, 0, 0, b""), cover_source=True)
        )
        return self._fix_mark_cover_source(album, new_filename)

    def _get_table_rows(
        self,
        album: AlbumEntity,
        some_pictures: list[Picture],
        pic_sources: dict[Picture, list[str]],
        source_picture: Picture,
        source_filename: str,
    ) -> Sequence[Sequence[RenderableType]]:
        (preview_image, preview_data) = self._make_embedded(album, source_filename, source_picture)
        pic_info = PictureInfo(self.create_mime_type, preview_image.width, preview_image.height, 24, len(preview_data), b"")
        preview_pic = Picture(pic_info, PictureType.COVER_FRONT, "")
        pictures = some_pictures + [(preview_pic, preview_image, preview_data)]
        return render_image_table(self.ctx, self.tagger.get(album.path), pictures, pic_sources)
