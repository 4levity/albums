import logging
from pathlib import Path
from typing import Any

from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album
from .base_check import Check, CheckResult, Fixer, ProblemCategory
from .helpers import ItemTotalPolicy, describe_track_number, ordered_tracks


logger = logging.getLogger(__name__)


class AbstractCheckTotalTag(Check):
    # subclass must override these two values:
    name = "check_name_placeholder"
    tag_name = "tag_name_placeholder"
    ###

    default_config = {"enabled": True, "policy": "consistent"}

    def init(self, check_config: dict[str, Any]):
        self.policy = ItemTotalPolicy.from_str(str(check_config.get("policy", self.default_config["policy"])))
        self.option_remove = f">> Remove tag {self.tag_name} from all tracks"

    def check(self, album: Album):
        if not album_is_basic_taggable(album):
            return None

        on_all_tracks = all(self.tag_name in t.tags for t in album.tracks)
        on_any_tracks = any(self.tag_name in t.tags for t in album.tracks)
        if self.policy == ItemTotalPolicy.ALWAYS and not on_all_tracks:
            message = f"{self.tag_name} policy {self.policy.name} but not on all tracks"
        elif self.policy == ItemTotalPolicy.NEVER and on_any_tracks:
            message = f"{self.tag_name} policy {self.policy.name} but appears on tracks"
        elif self.policy == ItemTotalPolicy.CONSISTENT and on_all_tracks != on_any_tracks:
            message = f"{self.tag_name} policy {self.policy.name} but it is on some tracks and not others"
        else:
            message = None

        if message:
            table = (["track", "filename"], [[describe_track_number(track), track.filename] for track in ordered_tracks(album)])
            option_free_text = False
            if self.policy == ItemTotalPolicy.ALWAYS:
                # TODO if total adds up and no conflicting values, this could have a fix too, but more complicated, maybe separate check
                return CheckResult(ProblemCategory.TAGS, message)
            else:
                options = [self.option_remove]
                option_automatic_index = 0
                return CheckResult(
                    ProblemCategory.TAGS,
                    message,
                    Fixer(lambda option: self._fix(album, option), options, option_free_text, option_automatic_index, table),
                )

    def _fix(self, album: Album, option: str | None) -> bool:
        if option != self.option_remove:
            raise ValueError(f"invalid option {option}")

        changed = False
        for track in album.tracks:
            if self.tag_name in track.tags:
                path = (self.ctx.library_root if self.ctx.library_root else Path(".")) / album.path / track.filename
                self.ctx.console.print(f"removing {self.tag_name} from {track.filename}")
                changed |= set_basic_tags(path, [(self.tag_name, None)])
        return changed
