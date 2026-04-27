from typing import Final, override

from rich.markup import escape

from albums.checks.helpers import show_tag

from ...types import Album, BasicTag, CheckResult, Fixer, FixResult
from ..base_check_tag_per_album import BaseCheckTagPerAlbum

OPTION_REMOVE_LABEL_PUBLISHER: Final = ">> Remove legacy label/publisher tags"
OPTION_USE_LABEL_PUBLISHER: Final = ">> Convert old label/publisher tag to organization"


class CheckPublisherTag(BaseCheckTagPerAlbum):
    name = "publisher-tag"
    tag = BasicTag.ORGANIZATION
    tag_description = "publisher/organization"

    @override
    def check(self, album: Album):
        legacy_publisher_values = set(v for t in album.tracks for v in t.get(BasicTag.OLD_LABEL, default=[])).union(
            v for t in album.tracks for v in t.get(BasicTag.OLD_PUBLISHER, default=[])
        )

        if legacy_publisher_values:
            organization = ""
            if any(track.has(BasicTag.ORGANIZATION) for track in album.tracks):
                message = "legacy tags label/publisher are present, correct tag organization is also present"
                options = [OPTION_REMOVE_LABEL_PUBLISHER]
            elif len(legacy_publisher_values) > 1:
                message = "legacy tags label/publisher are present and have conflicting values"
                options = [OPTION_REMOVE_LABEL_PUBLISHER]
            else:
                message = "legacy tags label/publisher have a value that can be used for organization"
                options = [OPTION_USE_LABEL_PUBLISHER, OPTION_REMOVE_LABEL_PUBLISHER]
                organization = legacy_publisher_values.pop()

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
                message,
                Fixer(lambda option: self._fix_legacy_tags(album, organization, option), options, False, option_automatic_index, table),
            )

        return super().check(album)

    def _fix_legacy_tags(self, album: Album, organization: str, option: str):
        set_organization = option == OPTION_USE_LABEL_PUBLISHER
        changed = False
        tagger = self.tagger.get(album.path)
        for track in sorted(track for track in album.tracks):
            if set_organization or track.has(BasicTag.OLD_LABEL) or track.has(BasicTag.OLD_PUBLISHER):
                with tagger.open(track.filename) as file:
                    if set_organization:
                        self.ctx.console.print(f"setting {BasicTag.ORGANIZATION.name}={organization} on {escape(track.filename)}")
                        file.set_tag(BasicTag.ORGANIZATION, organization)
                    for tag in (tag for tag in [BasicTag.OLD_LABEL, BasicTag.OLD_PUBLISHER] if track.has(tag)):
                        self.ctx.console.print(f"removing {tag.value} from {escape(track.filename)}")
                        file.set_tag(tag, None)
                changed = True
        return FixResult.of(changed)
