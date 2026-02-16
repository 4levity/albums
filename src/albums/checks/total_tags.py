from enum import Enum, auto
from typing import List

from rich.console import RenderableType
from rich.markup import escape

from ..app import Context
from ..library.metadata import set_basic_tags
from ..types import Album, CheckResult, Fixer, ProblemCategory
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


OPTION_REMOVE_TAG = ">> Remove tag"


def check_policy(
    ctx: Context, album: Album, policy: Policy, tag_name: str, corresponding_index_tag: str, option_free_text: bool = False
) -> CheckResult | None:
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
        if option_free_text or policy != Policy.ALWAYS:

            def _fix(option: str) -> bool:
                if option.startswith(OPTION_REMOVE_TAG):
                    value = None
                else:
                    value = option
                changed = False
                for track in album.tracks:
                    path = ctx.config.library / album.path / track.filename
                    if value is None and tag_name in track.tags:
                        ctx.console.print(f"removing {tag_name} from {track.filename}")
                        changed |= set_basic_tags(path, [(tag_name, None)])
                    if value is not None and (tag_name not in track.tags or track.tags[tag_name] != [value]):
                        ctx.console.print(f"setting {tag_name} on {track.filename}")
                        changed |= set_basic_tags(path, [(tag_name, value)])
                return changed

            options = [] if policy == Policy.ALWAYS else [f"{OPTION_REMOVE_TAG} {tag_name}"]
            option_automatic_index = 0 if len(options) == 1 else None
            if policy == Policy.NEVER:
                option_free_text = False
            table: tuple[list[str], List[List[RenderableType]]] = (
                ["track", "filename"],
                [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)],
            )
            fixer = Fixer(lambda option: _fix(option), options, option_free_text, option_automatic_index, table)
        else:
            fixer = None

        return CheckResult(ProblemCategory.TAGS, message, fixer)

    return None
