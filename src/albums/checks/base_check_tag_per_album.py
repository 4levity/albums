import logging
from typing import Any, Final

from rich.markup import escape

from ..tagger.folder import AlbumTagger, Cap
from ..types import Album, BasicTag, CheckResult, Fixer, FixResult
from .base_check import Check
from .tag_policy import Policy, check_policy

logger: Final = logging.getLogger(__name__)


class BaseCheckTagPerAlbum(Check):
    # subclass must define check name and album tag to check
    name: str
    tag: BasicTag

    # subclass may define additional config items, as well as description to use instead of tag.value
    default_config = {"enabled": True, "presence": "consistent"}
    tag_description: str = ""

    def init(self, check_config: dict[str, Any]):
        self.presence = Policy.from_str(str(check_config.get("presence", self.default_config["presence"])))
        if not self.tag_description:
            self.tag_description = self.tag.value
        self.option_remove_tag = f">> Remove {self.tag_description} from all tracks"

    def check(self, album: Album):
        return self.do_check(album, self.presence)

    def do_check(self, album: Album, presence: Policy):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None

        single_value_for_album = presence != Policy.NEVER
        presence_issue = check_policy(self.ctx, self.tagger.get(album.path), album, presence, self.tag, None, single_value_for_album)
        if presence_issue is not None:
            return presence_issue

        values = set(value for track in album.tracks for value in track.get(self.tag, default=[""]))
        if len(values) > 1:
            options = sorted(filter(None, values)) + [self.option_remove_tag]
            option_automatic_index = None
            option_free_text = True
            table = (
                ["filename", self.tag_description],
                [
                    [
                        track.filename,
                        ", ".join(track.get(self.tag, [""])) or "[italic]none[/italic]",
                    ]
                    for track in sorted(album.tracks)
                ],
            )
            return CheckResult(
                f"multiple values for {self.tag_description}: {', '.join(sorted((v or 'none') for v in values))}",
                Fixer(
                    lambda option: self._fix_set_tag(album, None if option == self.option_remove_tag else option),
                    options,
                    option_free_text,
                    option_automatic_index,
                    table,
                    f"Select {self.tag_description} for all tracks",
                ),
            )

    def _fix_set_tag(self, album: Album, option: str | None):
        tagger = self.tagger.get(album.path)
        changed = False
        for track in album.tracks:
            current_values = track.get(self.tag, default=[])
            if current_values and not option:
                self.ctx.console.print(f"Removing {self.tag_description} on {escape(track.filename)}", highlight=False)
                with tagger.open(track.filename) as tags:
                    tags.set_tag(self.tag, None)
                changed = True
            elif option and (len(current_values) != 1 or current_values[0] != option):
                self.ctx.console.print(f"Setting {self.tag_description} on {escape(track.filename)}", highlight=False)
                with tagger.open(track.filename) as tags:
                    tags.set_tag(self.tag, option)
                changed = True
        return FixResult.of(changed)
