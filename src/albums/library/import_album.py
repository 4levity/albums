import logging
from collections import defaultdict
from pathlib import Path
from string import Template

from pathvalidate import sanitize_filename, sanitize_filepath

from albums.tagger.types import BasicTag

from ..app import Context
from ..types import Album

logger = logging.getLogger(__name__)


def import_album(ctx: Context, source_path: Path, library_path: str, album: Album, extra: bool, recursive: bool):
    ctx.console.print(f"would import from {str(source_path)} -> {library_path}")


def make_library_paths(ctx: Context, album: Album):
    used_identifiers = set(ctx.config.default_import_path.get_identifiers() + ctx.config.default_import_path_various.get_identifiers())
    used_identifiers.update(identifier for path_T in ctx.config.more_import_paths for identifier in path_T.get_identifiers())
    unknown_identifiers = used_identifiers - {"artist", "a1", "A1", "album"}
    if unknown_identifiers:
        logger.warning(f"ignoring unknown template identifiers in import path template: {', '.join(unknown_identifiers)}")

    tag_values: defaultdict[BasicTag, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    for track in album.tracks:
        for tag, values in ((k, v) for k, v in track.tags.items() if k in {BasicTag.ALBUM, BasicTag.ALBUMARTIST, BasicTag.ARTIST}):
            for value in values:
                tag_values[tag][value] += 1
    tag_values_by_freq = dict(
        (tag, sorted(((value, count) for value, count in value_map.items()), key=lambda vc: vc[1], reverse=True))
        for tag, value_map in tag_values.items()
    )
    artist_v = ""
    various = False
    using_artist = "artist" in used_identifiers or "A1" in used_identifiers or "a1" in used_identifiers

    def safe_folder(folder: str) -> str:
        return sanitize_filename(folder, platform=ctx.config.path_compatibility)

    if BasicTag.ALBUMARTIST in tag_values_by_freq:
        albumartists = tag_values_by_freq[BasicTag.ALBUMARTIST]
        artist_v = safe_folder(albumartists[0][0])
        if len(albumartists) > 1 and using_artist:
            logger.warning(f"generating library path: more than one album artist value, using {artist_v}")
        if len(tag_values_by_freq.get(BasicTag.ARTIST, [])) > 1:
            various = True
    elif BasicTag.ARTIST in tag_values_by_freq:
        artists = tag_values_by_freq[BasicTag.ARTIST]
        artist_v = safe_folder(artists[0][0])
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
            album_v = safe_folder(albums[0][0])
            if len(albums) > 1:
                logger.warning(f"generating library path: more than one album artist value, using {album_v}")
        if not album_v:
            album_v = "Unknown Album"
            logger.warning(f"generating library path: no album artist or artist tags, using {artist_v}")

    a1_v = str.lower(safe_folder(artist_v[4] if artist_v.lower().startswith("the ") and len(artist_v) > 4 else artist_v[0]))
    substitutions = {"album": album_v, "artist": artist_v, "a1": a1_v, "A1": a1_v.upper()}
    logger.debug(f"substitutions for creating import paths: {substitutions}")

    def make_path(template: Template) -> str:
        return sanitize_filepath(template.safe_substitute(substitutions), platform=ctx.config.path_compatibility)

    default = make_path(ctx.config.default_import_path)
    default_various = make_path(ctx.config.default_import_path_various)
    more = [make_path(path_T) for path_T in ctx.config.more_import_paths]
    return [default_various, *more, default] if various else [default, *more, default_various]
