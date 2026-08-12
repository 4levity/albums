from typing import Final, override

from rich.markup import escape

from ...entities import Album
from ...tagger.types import BasicField
from ...tagger.vorbis import LEGACY_VORBIS_FIELDS
from ..base_check import Check
from ..check_types import CheckResult, Fixer, FixResult

LEGACY_TO_BASIC: Final[dict[str, BasicField]] = dict(LEGACY_VORBIS_FIELDS)

OPTION_CONVERT_LEGACY = ">> Convert legacy fields to standard fields"


class CheckLegacyFields(Check):
    name = "legacy-fields"
    default_config = {"enabled": True}

    @override
    def check(self, album: Album):
        if not any(track.legacy_fields for track in album.tracks):
            return None

        all_legacy_names: set[str] = set()
        for track in album.tracks:
            all_legacy_names.update(track.legacy_fields)

        option_automatic_index = 0
        table = (
            ["filename", "convert fields"],
            [[escape(track.filename), ", ".join(track.legacy_fields)] for track in sorted(album.tracks)],
        )

        return CheckResult(
            f"Legacy fields {', '.join(sorted(all_legacy_names))} found",
            Fixer(
                lambda option: self._fix_legacy_fields(album),
                [OPTION_CONVERT_LEGACY],
                False,
                option_automatic_index,
                table,
            ),
        )

    def _fix_legacy_fields(self, album: Album):
        changed = False
        tagger = self.tagger.get(album.path)

        for track in sorted(track for track in album.tracks if track.legacy_fields):
            track_fields = track.field_dict()
            with tagger.open(track.filename) as tag:
                basic_fields = set(filter(None, (LEGACY_TO_BASIC.get(legacy_name) for legacy_name in track.legacy_fields)))
                for field in basic_fields:
                    values = track_fields[field]
                    self.ctx.console.print(f"setting {field.name}={values} on {escape(track.filename)}", highlight=False)
                    tag.set_field(field, values)

                for legacy_name in track.legacy_fields:
                    self.ctx.console.print(f"removing {legacy_name} from {escape(track.filename)}", highlight=False)
                    tag.set_field(legacy_name, None)

            changed = True

        return FixResult.of(changed)
