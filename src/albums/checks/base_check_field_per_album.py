import logging
from typing import Any, Final

from rich.markup import escape

from ..entities import Album
from ..tagger.folder import AlbumTagger, Cap
from ..tagger.types import BasicField
from .base_check import Check
from .check_types import CheckResult, Fixer, FixResult
from .field_policy import Policy, check_policy

logger: Final = logging.getLogger(__name__)


class BaseCheckFieldPerAlbum(Check):
    # subclass must define check name and album field to check
    name: str
    field: BasicField

    # subclass may override
    # force presence to NEVER when album is a mix of vorbis-comment and non-vorbis-comment tracks
    vorbis_only: bool = False
    # the value for the album can be a multi-value (still needs to be the same on all tracks)
    tuple_value: bool = False

    # subclass may define additional config items, as well as description to use instead of tag.value
    default_config = {"enabled": True, "presence": "consistent"}
    field_description: str = ""

    def init(self, check_config: dict[str, Any]):
        self.presence = Policy.from_str(str(check_config.get("presence", self.default_config["presence"])))
        if not self.field_description:
            self.field_description = self.field.value
        self.option_remove_field = f">> Remove {self.field_description} from all tracks"

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_FIELDS) for track in album.tracks):
            return None

        if (
            self.vorbis_only
            and self.presence != Policy.NEVER
            and not all(AlbumTagger.supports(track.filename, Cap.VORBIS_COMMENT) for track in album.tracks)
        ):
            # this field is only supported for vorbis comments, so if any track is not vorbis comment, the only reasonable policy is NEVER
            # (only makes a difference if the album is a mix of vorbis and non-vorbis tracks)
            presence = Policy.NEVER
        else:
            presence = self.presence

        single_value_for_album = presence != Policy.NEVER
        presence_issue = check_policy(self.ctx, self.tagger.get(album.path), album, presence, self.field, None, single_value_for_album)
        if presence_issue is not None:
            return presence_issue

        if self.tuple_value:
            values = set(track.get(self.field, default=()) for track in album.tracks)
            options = sorted(", ".join(v) for v in values) + [self.option_remove_field]
        else:
            values = set(value for track in album.tracks for value in track.get(self.field, default=[""]))
            options = sorted(filter(None, values)) + [self.option_remove_field]

        if len(values) > 1:
            option_automatic_index = None
            option_free_text = True
            table = (
                ["filename", self.field_description],
                [
                    [
                        track.filename,
                        ", ".join(track.get(self.field, [""])) or "[italic]none[/italic]",
                    ]
                    for track in sorted(album.tracks)
                ],
            )
            return CheckResult(
                f"multiple values for {self.field_description}: {', '.join(sorted((str(v) or 'none') for v in values))}",
                Fixer(
                    lambda option: self._fix_set_field(album, None if option == self.option_remove_field else option),
                    options,
                    option_free_text,
                    option_automatic_index,
                    table,
                    f"Select {self.field_description} for all tracks",
                ),
            )

    def _fix_set_field(self, album: Album, option: str | None):
        tagger = self.tagger.get(album.path)
        changed = False
        for track in album.tracks:
            current_values = track.get(self.field, default=[])
            if current_values and not option:
                self.ctx.console.print(f"Removing {self.field_description} on {escape(track.filename)}", highlight=False)
                with tagger.open(track.filename) as tag:
                    tag.set_field(self.field, None)
                changed = True
            elif option:
                set_value = None
                if self.tuple_value:
                    option_value = list(option.split(", ")) if (option and self.tuple_value) else option
                    if list(current_values) != option_value:
                        set_value = option_value
                elif len(current_values) != 1 or current_values[0] != option:
                    set_value = option
                if set_value is not None:
                    self.ctx.console.print(f"Setting {self.field_description} on {escape(track.filename)}", highlight=False)
                    with tagger.open(track.filename) as tag:
                        tag.set_field(self.field, set_value)
                    changed = True
        return FixResult.of(changed)
