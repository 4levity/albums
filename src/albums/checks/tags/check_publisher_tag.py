from typing import override

from rich.markup import escape

from albums.checks.helpers import show_tag

from ...types import Album, BasicTag, CheckResult, Fixer, FixResult
from ..base_check_tag_per_album import BaseCheckTagPerAlbum


class CheckPublisherTag(BaseCheckTagPerAlbum):
    name = "publisher-tag"
    tag = BasicTag.ORGANIZATION
    tag_description = "publisher/organization"

    @override
    def check(self, album: Album):
        if any((track.has(BasicTag.OLD_LABEL) or track.has(BasicTag.OLD_PUBLISHER)) for track in album.tracks):
            options = [">> Remove legacy label/publisher tags"]
            option_automatic_index = 0
            table = (
                ["filename", "organization", "label", "publisher"],
                [
                    [
                        escape(track.filename),
                        show_tag(track.get(BasicTag.ORGANIZATION, default=None)),
                        show_tag(track.get(BasicTag.OLD_LABEL, default=None)),
                        show_tag(track.get(BasicTag.OLD_PUBLISHER, default=None)),
                    ]
                    for track in sorted(album.tracks)
                ],
            )
            return CheckResult(
                "legacy tags 'label' or 'publisher' are present",
                Fixer(lambda _: self._fix_remove_legacy_tags(album), options, False, option_automatic_index, table),
            )
        return super().check(album)

    def _fix_remove_legacy_tags(self, album: Album):
        changed = False
        tagger = self.tagger.get(album.path)
        for track in sorted(track for track in album.tracks if (track.has(BasicTag.OLD_LABEL) or track.has(BasicTag.OLD_PUBLISHER))):
            with tagger.open(track.filename) as tags:
                for tag in (tag for tag in [BasicTag.OLD_LABEL, BasicTag.OLD_PUBLISHER] if track.has(tag)):
                    self.ctx.console.print(f"removing {tag.value} from {escape(track.filename)}")
                    tags.set_tag(tag, None)
            changed = True
        return FixResult.of(changed)
