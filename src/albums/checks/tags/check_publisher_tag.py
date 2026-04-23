import logging
from typing import Any, Final

from rich.markup import escape

from ...tagger.folder import AlbumTagger, Cap
from ...types import Album, BasicTag, CheckResult, Fixer, FixResult
from ..base_check import Check
from ..tag_policy import Policy, check_policy

logger: Final = logging.getLogger(__name__)

OPTION_REMOVE_ORGANIZATION: Final = ">> Remove organization (publisher) from all tracks"


class CheckPublisherTag(Check):
    name = "publisher-tag"
    default_config = {"enabled": True, "presence": "consistent"}

    def init(self, check_config: dict[str, Any]):
        self.presence = Policy.from_str(str(check_config.get("presence", self.default_config["presence"])))

    def check(self, album: Album):
        if not all(AlbumTagger.supports(track.filename, Cap.BASIC_TAGS) for track in album.tracks):
            return None

        single_value_for_album = self.presence != Policy.NEVER
        presence_issue = check_policy(
            self.ctx, self.tagger.get(album.path), album, self.presence, BasicTag.ORGANIZATION, None, single_value_for_album
        )
        if presence_issue is not None:
            return presence_issue

        publishers = set(pub for track in album.tracks for pub in track.get(BasicTag.ORGANIZATION, default=[""]))
        if len(publishers) > 1:
            options = sorted(filter(None, publishers)) + [OPTION_REMOVE_ORGANIZATION]
            option_automatic_index = None
            option_free_text = True
            table = (
                ["filename", "organization/publisher"],
                [
                    [
                        track.filename,
                        ", ".join(track.get(BasicTag.ORGANIZATION, [""])) or "[italic]none[/italic]",
                    ]
                    for track in sorted(album.tracks)
                ],
            )
            return CheckResult(
                f"multiple values for publisher (organization): {', '.join(sorted((p or 'none') for p in publishers))}",
                Fixer(
                    lambda option: self._fix_set_publisher(album, None if option == OPTION_REMOVE_ORGANIZATION else option),
                    options,
                    option_free_text,
                    option_automatic_index,
                    table,
                    "Select a publisher/organization for all tracks",
                ),
            )

    def _fix_set_publisher(self, album: Album, option: str | None):
        tagger = self.tagger.get(album.path)
        changed = False
        for track in album.tracks:
            org = track.get(BasicTag.ORGANIZATION, default=[])
            if org and not option:
                self.ctx.console.print(f"Removing organization/publisher on {escape(track.filename)}", highlight=False)
                with tagger.open(track.filename) as tags:
                    tags.set_tag(BasicTag.ORGANIZATION, None)
                changed = True
            elif option and (len(org) != 1 or org[0] != option):
                self.ctx.console.print(f"Setting organization/publisher on {escape(track.filename)}", highlight=False)
                with tagger.open(track.filename) as tags:
                    tags.set_tag(BasicTag.ORGANIZATION, option)
                changed = True
        return FixResult.of(changed)
