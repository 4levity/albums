import logging
from collections import defaultdict
from string import Template
from typing import Sequence

from pathvalidate import sanitize_filename, sanitize_filepath

from ..app import Context
from ..tagger.types import BasicTag
from ..types import Album

logger = logging.getLogger(__name__)


def show_template_path_help(ctx: Context):
    ctx.console.print("Available substitution variables: [bold]album[/bold], [bold]artist[/bold], [bold]A1[/bold], [bold]a1[/bold]")


def make_template_path(ctx: Context, album: Album, t_artist: Template, t_various: Template) -> str:
    return make_template_paths(ctx, album, t_artist, t_various)[0]


def make_template_paths(ctx: Context, album: Album, t_artist: Template, t_various: Template, t_more: Sequence[Template] = []) -> Sequence[str]:
    used_identifiers = set(t_artist.get_identifiers() + t_various.get_identifiers())
    used_identifiers.update(identifier for path_T in t_more for identifier in path_T.get_identifiers())
    unknown_identifiers = used_identifiers - {"artist", "a1", "A1", "album"}
    if unknown_identifiers:
        logger.warning(f"ignoring unknown template identifiers: {', '.join(unknown_identifiers)}")

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
            template.safe_substitute(substitutions),
            replacement_text=ctx.config.path_replace_invalid,
            platform=ctx.config.path_compatibility,
        )

    path_artist = make_path(t_artist)
    path_various = make_path(t_various)
    more = [make_path(path_T) for path_T in t_more]
    return [path_various, *more, path_artist] if various else [path_artist, *more, path_various]
