import glob
import logging
from collections import defaultdict
from itertools import chain
from pathlib import Path
from string import Template

from pathvalidate import sanitize_filename, sanitize_filepath
from rich.markup import escape

from albums.library.synchronizer import copy_files_with_progress
from albums.tagger.types import BasicTag
from albums.types import Album

from ..app import Context

logger = logging.getLogger(__name__)


def import_album(ctx: Context, source_path: Path, destination_path_in_library: str, album: Album, extra: bool, recursive: bool):
    src = source_path.resolve()
    if not src.is_dir():
        logger.error(f"import_album: not a directory: {str(src)}")
        raise SystemExit(1)

    root_ctx = ctx.parent if ctx.parent is not None else ctx
    destination_path = root_ctx.config.library / destination_path_in_library
    dest = Path(destination_path).resolve()
    if dest.exists():
        logger.error(f"import_album: destination already exists: {str(dest)}")
        raise SystemExit(1)
    if extra or recursive:
        filenames = glob.iglob("**", root_dir=src, recursive=recursive)
    else:
        filenames = chain((track.filename for track in album.tracks), (file.filename for file in album.picture_files))

    to_copy: list[tuple[Path, Path, int]] = []  # list of (source, destination, size)
    for filename in filenames:
        src_path = src / filename
        if src_path.is_file():
            to_copy.append((src_path, dest / filename, src_path.stat().st_size))
    if not to_copy:
        raise RuntimeError("unexpected: no files to copy?")

    copy_files_with_progress(ctx, to_copy)

    ctx.console.print(f"Imported album to {escape(destination_path_in_library)} (will be added to library on next scan)")
    # TODO add album to database immediately + include cover source mark or ignored checks from import process


def make_library_paths(ctx: Context, album: Album):
    used_identifiers = set(ctx.config.default_import_path.get_identifiers() + ctx.config.default_import_path_various.get_identifiers())
    used_identifiers.update(identifier for path_T in ctx.config.more_import_paths for identifier in path_T.get_identifiers())
    unknown_identifiers = used_identifiers - {"artist", "a1", "A1", "album"}
    if unknown_identifiers:
        logger.warning(f"ignoring unknown template identifiers in import path template: {', '.join(unknown_identifiers)}")

    tag_values: defaultdict[BasicTag, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    for track in album.tracks:
        for tag, values in ((k, v) for k, v in track.tag_dict().items() if k in {BasicTag.ALBUM, BasicTag.ALBUMARTIST, BasicTag.ARTIST}):
            for value in values:
                tag_values[tag][value] += 1
    tag_values_by_freq = dict(
        (tag, sorted(((value, count) for value, count in value_map.items()), key=lambda vc: vc[1], reverse=True))
        for tag, value_map in tag_values.items()
    )
    artist_v = ""
    various = False
    using_artist = "artist" in used_identifiers or "A1" in used_identifiers or "a1" in used_identifiers

    def safe_path_element(folder: str) -> str:
        folder = folder.replace("/", ctx.config.path_replace_slash)
        return sanitize_filename(folder, replacement_text=ctx.config.path_replace_invalid, platform=ctx.config.path_compatibility)

    if BasicTag.ALBUMARTIST in tag_values_by_freq:
        albumartists = tag_values_by_freq[BasicTag.ALBUMARTIST]
        artist_v = safe_path_element(albumartists[0][0])
        if len(albumartists) > 1 and using_artist:
            logger.warning(f"generating library path: more than one album artist value, using {artist_v}")
        if len(tag_values_by_freq.get(BasicTag.ARTIST, [])) > 1:
            various = True
    elif BasicTag.ARTIST in tag_values_by_freq:
        artists = tag_values_by_freq[BasicTag.ARTIST]
        artist_v = safe_path_element(artists[0][0])
        if len(artists) > 1:
            various = True
            if using_artist:
                logger.warning(f"generating library path: no album artist and more than one artist value, using {artist_v}")
    if not artist_v:
        artist_v = "Unknown Album"
        logger.warning(f"generating library path: no album artist or artist tags, using {artist_v}")

    album_v = ""
    if "album" in used_identifiers:
        if BasicTag.ALBUM in tag_values_by_freq:
            albums = tag_values_by_freq[BasicTag.ALBUM]
            album_v = safe_path_element(albums[0][0])
            if len(albums) > 1:
                logger.warning(f"generating library path: more than one album artist value, using {album_v}")
        if not album_v:
            album_v = "Unknown Album"
            logger.warning(f"generating library path: no album artist or artist tags, using {artist_v}")

    a1_v = str.lower(safe_path_element(artist_v[4] if artist_v.lower().startswith("the ") and len(artist_v) > 4 else artist_v[0]))
    if a1_v.isnumeric():
        a1_v = "#"

    substitutions = {"album": album_v, "artist": artist_v, "a1": a1_v, "A1": a1_v.upper()}
    logger.debug(f"substitutions for creating import paths: {substitutions}")

    def make_path(template: Template) -> str:
        return sanitize_filepath(
            template.safe_substitute(substitutions), replacement_text=ctx.config.path_replace_invalid, platform=ctx.config.path_compatibility
        )

    default = make_path(ctx.config.default_import_path)
    default_various = make_path(ctx.config.default_import_path_various)
    more = [make_path(path_T) for path_T in ctx.config.more_import_paths]
    return [default_various, *more, default] if various else [default, *more, default_various]
