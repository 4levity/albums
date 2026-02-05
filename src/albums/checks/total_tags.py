from enum import Enum, auto
from pathlib import Path

from rich.markup import escape

from ..app import Context
from ..library.metadata import set_basic_tags
from ..types import Album
from .base_check import CheckResult, Fixer, ProblemCategory
from .helpers import describe_track_number, ordered_tracks


class Policy(Enum):
    CONSISTENT = auto()
    ALWAYS = auto()
    NEVER = auto()

    @classmethod
    def from_str(cls, selection: str):
        for policy in cls:
            if str.lower(policy.name) == str.lower(selection):
                return policy
        raise ValueError(f'invalid total_tags.Policy "{selection}"')


def check_policy(ctx: Context, album: Album, policy: Policy, tag_name: str, corresponding_index_tag: str) -> CheckResult | None:
    on_all_tracks = all(tag_name in t.tags for t in album.tracks)
    on_any_tracks = any(tag_name in t.tags for t in album.tracks)
    any_total_without_index = any(tag_name in t.tags and corresponding_index_tag not in t.tags for t in album.tracks)

    if any_total_without_index:
        message = f"{tag_name} appears on tracks without {corresponding_index_tag}"
        # if policy != always, automated fix to remove all totals will solve this
    elif policy == Policy.ALWAYS and not on_all_tracks:
        message = f"{tag_name} policy={policy.name} but it is not on all tracks"
    elif policy == Policy.NEVER and on_any_tracks:
        message = f"{tag_name} policy={policy.name} but it appears on tracks"
    elif policy == Policy.CONSISTENT and on_all_tracks != on_any_tracks:
        message = f"{tag_name} policy={policy.name} but it is on some tracks and not others"
    else:
        message = None

    if message:
        if policy == Policy.ALWAYS:
            # this helper can only remove values, so "always" policy limits automatic fixability
            return CheckResult(ProblemCategory.TAGS, message)
        else:
            option_free_text = False
            option_automatic_index = 0
            table = (["track", "filename"], [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)])
            return CheckResult(
                ProblemCategory.TAGS,
                message,
                Fixer(
                    lambda _: _remove_tag(ctx, tag_name, album),
                    [f">> Remove tag {tag_name} from all tracks"],
                    option_free_text,
                    option_automatic_index,
                    table,
                ),
            )


def _remove_tag(ctx: Context, tag_name: str, album: Album) -> bool:
    changed = False
    for track in album.tracks:
        if tag_name in track.tags:
            path = (ctx.library_root if ctx.library_root else Path(".")) / album.path / track.filename
            ctx.console.print(f"removing {tag_name} from {track.filename}")
            changed |= set_basic_tags(path, [(tag_name, None)])
    return changed
