import logging
from typing import Any, Collection

from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...types import Album, BasicTag, CheckResult, Fixer, FixResult
from ..base_check import Check

logger = logging.getLogger(__name__)


ALL_MBID_TAGS = frozenset(
    (
        BasicTag.MUSICBRAINZ_ALBUMARTISTID,
        BasicTag.MUSICBRAINZ_ALBUMID,
        BasicTag.MUSICBRAINZ_ARTISTID,
        BasicTag.MUSICBRAINZ_COMPOSERID,
        BasicTag.MUSICBRAINZ_DISCID,
        BasicTag.MUSICBRAINZ_ORIGINALALBUMID,
        BasicTag.MUSICBRAINZ_ORIGINALARTISTID,
        BasicTag.MUSICBRAINZ_TRACKID,
        BasicTag.MUSICBRAINZ_TRMID,
        BasicTag.MUSICBRAINZ_RELEASEGROUPID,
        BasicTag.MUSICBRAINZ_RELEASETRACKID,
        BasicTag.MUSICBRAINZ_WORKID,
    )
)

DEPRECATED_MBID_TAGS = frozenset((BasicTag.MUSICBRAINZ_TRMID,))


class CheckMusicBrainzTags(Check):
    name = "musicbrainz-tags"
    default_config = {"enabled": True, "remove_all": False, "remove_deprecated": True}

    def init(self, check_config: dict[str, Any]):
        self.remove_all = bool(check_config.get("remove_all", self.default_config["remove_all"]))
        self.remove_deprecated = bool(check_config.get("remove_deprecated", self.default_config["remove_deprecated"]))
        if self.remove_all and not self.remove_deprecated:
            raise ValueError("musicbrainz-tags.remove_deprecated must be enabled if remove_all is enabled")

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None

        if not any(any(track.has(mbid) for mbid in ALL_MBID_TAGS) for track in album.tracks):
            return None

        if self.remove_all:
            options = [">> Remove all MusicBrainz tags"]
            option_automatic_index = 0
            return CheckResult(
                "MusicBrainz tags found and remove_all is enabled",
                Fixer(lambda _: self._remove_tags(album, ALL_MBID_TAGS), options, False, option_automatic_index),
            )
        elif self.remove_deprecated and any(any(track.has(mbid) for mbid in DEPRECATED_MBID_TAGS) for track in album.tracks):
            options = [">> Remove deprecated MusicBrainz tags"]
            option_automatic_index = 0
            return CheckResult(
                "Deprecated MusicBrainz tags found and remove_deprecated is enabled",
                Fixer(lambda _: self._remove_tags(album, DEPRECATED_MBID_TAGS), options, False, option_automatic_index),
            )

        return self._check_consistent_tag(album, BasicTag.MUSICBRAINZ_ALBUMID) or (
            self._check_consistent_tag(album, BasicTag.MUSICBRAINZ_ALBUMARTISTID)
        )

    def _check_consistent_tag(self, album: Album, check_tag: BasicTag) -> CheckResult | None:
        values = set(v for track in album.tracks for v in track.get(check_tag, ["none"]))
        if len(values) > 1:
            options = [f">> Remove {check_tag.name} tags", ">> Remove all MusicBrainz tags"]
            option_automatic_index = 0  # automatic/default: only remove the conflicting MBID
            return CheckResult(
                f"{check_tag.name} is not the same on all tracks (values = {', '.join(sorted(values))})",
                Fixer(lambda option: self._remove_tags(album, ALL_MBID_TAGS, option, check_tag), options, False, option_automatic_index),
            )

    def _remove_tags(self, album: Album, default_remove_tags: Collection[BasicTag], option: str = "", option_match_tag: BasicTag | None = None):
        tagger = self.tagger.get(album.path)
        changed = False
        if option and option_match_tag and option_match_tag.name in option:
            remove_tags = [option_match_tag]
        else:
            remove_tags = sorted(default_remove_tags)

        for track in album.tracks:
            remove = [tag for tag in remove_tags if track.has(tag)]
            if remove:
                self.ctx.console.print(f"Removing MusicBrainz tags ({', '.join(remove)}) from {escape(track.filename)}", highlight=False)
                with tagger.open(track.filename) as tags:
                    for tag_to_remove in remove:
                        tags.set_tag(tag_to_remove, None)
                changed = True
        return FixResult.of(changed)
