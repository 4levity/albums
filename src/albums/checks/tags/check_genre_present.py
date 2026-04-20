import logging
from typing import Any, Final

from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...types import Album, BasicTag, CheckResult, Fixer, FixResult
from ..base_check import Check
from ..tag_policy import Policy, check_policy

logger: Final = logging.getLogger(__name__)


class CheckGenrePresent(Check):
    name = "genre-present"
    default_config = {
        "enabled": True,
        "presence": "consistent",
        "per_track": False,
        "select_genres": ["Blues", "Classical", "Country", "Electronic", "Heavy Metal", "Hip-Hop", "Jazz", "Rock", "Soundtracks"],
    }

    def init(self, check_config: dict[str, Any]):
        self.presence = Policy.from_str(str(check_config.get("presence", self.default_config["presence"])))
        self.per_track = bool(check_config.get("per_track", self.default_config["per_track"]))
        self.select_genres: list[str] = check_config.get("select_genres", self.default_config["select_genres"])
        if not isinstance(self.select_genres, list) or any(not isinstance(genre, str) for genre in self.select_genres):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("genre-present.select_genres must be a list of genres")
        # TODO validate that genre list is valid, if a list of valid genres is configured

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None

        # TODO check_policy should take an option list for its fixer
        single_value_for_album = self.presence != Policy.NEVER
        presence_issue = check_policy(self.ctx, self.tagger.get(album.path), album, self.presence, BasicTag.GENRE, None, single_value_for_album)
        if presence_issue is not None:
            return presence_issue

        if not self.per_track:
            # all tracks must have same genre(s) or none
            match_genre = album.tracks[0].get(BasicTag.GENRE, default=None)
            for track in sorted(album.tracks):
                genre = track.get(BasicTag.GENRE, default=None)
                if (genre is None) != (match_genre is None) or genre != match_genre:
                    # TODO found genres first, ranked by number of matching tracks, followed by remaining select_genres
                    options = self.select_genres
                    option_automatic_index = None
                    option_free_text = True
                    table = (
                        ["filename", "artist", "genre"],
                        [
                            [
                                track.filename,
                                "/".join(track.get(BasicTag.ARTIST, [""])),
                                "/".join(track.get(BasicTag.GENRE, [""])),
                            ]
                            for track in sorted(album.tracks)
                        ],
                    )
                    example = f"{'none' if genre is None else '/'.join(genre)} and {'none' if match_genre is None else '/'.join(match_genre)}"
                    return CheckResult(
                        f"genre per_track is false, but tracks have different genres, example {example}",
                        Fixer(
                            lambda option: self._fix_set_genre(album, option),
                            options,
                            option_free_text,
                            option_automatic_index,
                            table,
                            "Select a genre for all tracks",
                        ),
                    )

    def _fix_set_genre(self, album: Album, option: str):
        # TODO: check if option is a "valid" genre (may be free text)
        tagger = self.tagger.get(album.path)
        changed = False
        for track in album.tracks:
            if "/".join(track.get(BasicTag.GENRE, default=[""])) != option:
                self.ctx.console.print(f'Setting genre to "{option}" on {escape(track.filename)}', highlight=False)
                with tagger.open(track.filename) as tags:
                    tags.set_tag(BasicTag.GENRE, option)
                changed = True
        return FixResult.of(changed)
