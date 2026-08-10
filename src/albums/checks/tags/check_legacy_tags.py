from typing import Final, override

from rich.markup import escape

from ...tagger.types import BasicTag
from ...tagger.vorbis import LEGACY_VORBIS_TAGS
from ...types import Album, CheckResult, Fixer, FixResult
from ..base_check import Check

LEGACY_TO_BASIC: Final[dict[str, BasicTag]] = dict(LEGACY_VORBIS_TAGS)

OPTION_CONVERT_LEGACY = ">> Convert legacy tags to standard tags"


class CheckLegacyTags(Check):
    name = "legacy-tags"
    default_config = {"enabled": True}

    @override
    def check(self, album: Album):
        if not any(track.legacy_tags for track in album.tracks):
            return None

        all_legacy_names: set[str] = set()
        for track in album.tracks:
            all_legacy_names.update(track.legacy_tags)

        option_automatic_index = 0
        table = (
            ["filename", "convert tags"],
            [[escape(track.filename), ", ".join(track.legacy_tags)] for track in sorted(album.tracks)],
        )

        return CheckResult(
            f"Legacy tags {', '.join(sorted(all_legacy_names))} found",
            Fixer(
                lambda option: self._fix_legacy_tags(album),
                [OPTION_CONVERT_LEGACY],
                False,
                option_automatic_index,
                table,
            ),
        )

    def _fix_legacy_tags(self, album: Album):
        changed = False
        tagger = self.tagger.get(album.path)

        for track in sorted(track for track in album.tracks if track.legacy_tags):
            track_tags = track.tag_dict()
            with tagger.open(track.filename) as file:
                basic_tags = set(filter(None, (LEGACY_TO_BASIC.get(legacy_name) for legacy_name in track.legacy_tags)))
                for tag in basic_tags:
                    values = track_tags[tag]
                    self.ctx.console.print(f"setting {tag.name}={values} on {escape(track.filename)}", highlight=False)
                    file.set_tag(tag, values)

                for legacy_name in track.legacy_tags:
                    self.ctx.console.print(f"removing {legacy_name} from {escape(track.filename)}", highlight=False)
                    file.set_tag(legacy_name, None)

            changed = True

        return FixResult.of(changed)
