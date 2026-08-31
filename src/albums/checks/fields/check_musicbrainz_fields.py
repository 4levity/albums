import logging
from typing import Any, Collection, Final

from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.entities import Album
from albums.tagger import AlbumTagger, BasicField, Cap

logger: Final = logging.getLogger(__name__)


ALL_MBID_FIELDS: Final = frozenset(
    (
        BasicField.MUSICBRAINZ_ALBUMARTISTID,
        BasicField.MUSICBRAINZ_ALBUMID,
        BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY,
        BasicField.MUSICBRAINZ_ALBUMRELEASETYPE,
        BasicField.MUSICBRAINZ_ARRANGERID,
        BasicField.MUSICBRAINZ_ARTISTID,
        BasicField.MUSICBRAINZ_COMPOSERID,
        BasicField.MUSICBRAINZ_CONDUCTORID,
        BasicField.MUSICBRAINZ_DIRECTORID,
        BasicField.MUSICBRAINZ_DISCID,
        BasicField.MUSICBRAINZ_LYRICISTID,
        BasicField.MUSICBRAINZ_MIXERID,
        BasicField.MUSICBRAINZ_ORIGINALALBUMID,
        BasicField.MUSICBRAINZ_ORIGINALARTISTID,
        BasicField.MUSICBRAINZ_ORIGINALRELEASEID,
        BasicField.MUSICBRAINZ_PRODUCERID,
        BasicField.MUSICBRAINZ_TRACKID,
        BasicField.MUSICBRAINZ_TRMID,
        BasicField.MUSICBRAINZ_RELEASEARTISTID,
        BasicField.MUSICBRAINZ_RELEASEGROUPID,
        BasicField.MUSICBRAINZ_RELEASETRACKID,
        BasicField.MUSICBRAINZ_REMIXERID,
        BasicField.MUSICBRAINZ_WORKID,
    )
)

DEPRECATED_MBID_FIELDS: Final = frozenset((BasicField.MUSICBRAINZ_TRMID,))


class CheckMusicBrainzFields(Check):
    name = "musicbrainz-fields"
    default_config = {"enabled": True, "remove_all": False, "remove_deprecated": True}

    def init(self, check_config: dict[str, Any]):
        self.remove_all = bool(check_config.get("remove_all", self.default_config["remove_all"]))
        self.remove_deprecated = bool(check_config.get("remove_deprecated", self.default_config["remove_deprecated"]))
        if self.remove_all and not self.remove_deprecated:
            raise ValueError("musicbrainz-fields.remove_deprecated must be enabled if remove_all is enabled")

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_FIELDS) for track in album.tracks):
            return None

        if not any(any(track.has(mbid) for mbid in ALL_MBID_FIELDS) for track in album.tracks):
            return None

        if self.remove_all:
            options = [">> Remove all MusicBrainz fields"]
            option_automatic_index = 0
            return CheckResult(
                "MusicBrainz fields found and remove_all is enabled",
                Fixer(lambda _: self._remove_fields(album, ALL_MBID_FIELDS), options, False, option_automatic_index),
            )
        elif self.remove_deprecated and any(any(track.has(mbid) for mbid in DEPRECATED_MBID_FIELDS) for track in album.tracks):
            options = [">> Remove deprecated MusicBrainz fields"]
            option_automatic_index = 0
            return CheckResult(
                "Deprecated MusicBrainz fields found and remove_deprecated is enabled",
                Fixer(lambda _: self._remove_fields(album, DEPRECATED_MBID_FIELDS), options, False, option_automatic_index),
            )

        return (
            self._check_consistent_field(album, BasicField.MUSICBRAINZ_ALBUMID)
            or self._check_consistent_field(album, BasicField.MUSICBRAINZ_ALBUMARTISTID)
            or self._check_consistent_field(album, BasicField.MUSICBRAINZ_ALBUMRELEASECOUNTRY)
            or self._check_consistent_field(album, BasicField.MUSICBRAINZ_ALBUMRELEASETYPE)
        )

    def _check_consistent_field(self, album: Album, check_field: BasicField) -> CheckResult | None:
        values = set(v for track in album.tracks for v in track.get(check_field, ["none"]))
        if len(values) > 1:
            options = [f">> Remove {check_field.name} fields", ">> Remove all MusicBrainz fields"]
            option_automatic_index = 0  # automatic/default: only remove the conflicting MBID
            return CheckResult(
                f"{check_field.name} is not the same on all tracks (values = {', '.join(sorted(values))})",
                Fixer(lambda option: self._remove_fields(album, ALL_MBID_FIELDS, option, check_field), options, False, option_automatic_index),
            )

    def _remove_fields(
        self, album: Album, default_remove_fields: Collection[BasicField], option: str = "", option_match_field: BasicField | None = None
    ):
        tagger = self.tagger.get(album.path)
        changed = False
        if option and option_match_field and option_match_field.name in option:
            remove_fields = [option_match_field]
        else:
            remove_fields = sorted(default_remove_fields)

        for track in album.tracks:
            remove = [field for field in remove_fields if track.has(field)]
            if remove:
                self.ctx.console.print(f"Removing MusicBrainz fields ({', '.join(remove)}) from {escape(track.filename)}", highlight=False)
                with tagger.open(track.filename) as tag:
                    for field_to_remove in remove:
                        tag.set_field(field_to_remove, None)
                changed = True
        return FixResult.of(changed)
