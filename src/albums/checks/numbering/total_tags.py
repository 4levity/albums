from enum import Enum, auto

from rich.markup import escape

from ...app import Context
from ...tagger.folder import AlbumTagger
from ...tagger.types import BasicTag
from ...types import Album, CheckResult, Fixer
from ..helpers import describe_track_number, ordered_tracks


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
    ctx: Context,
    tagger: AlbumTagger,
    album: Album,
    policy: Policy,
    tag: BasicTag,
    corresponding_index_tag: BasicTag,
    option_free_text: bool = False,
) -> CheckResult | None:
    on_all_tracks = all(t.has(tag) for t in album.tracks)
    on_any_tracks = any(t.has(tag) for t in album.tracks)
    any_total_without_index = any(t.has(tag) and not t.has(corresponding_index_tag) for t in album.tracks)

    if any_total_without_index:
        message = f"{tag} appears on tracks without {corresponding_index_tag}"
        # if policy != always, automated fix to remove all totals will solve this
    elif policy == Policy.ALWAYS and not on_all_tracks:
        message = f"{tag} policy={policy.name} but it is not on all tracks"
    elif policy == Policy.NEVER and on_any_tracks:
        message = f"{tag} policy={policy.name} but it appears on tracks"
    elif policy == Policy.CONSISTENT and on_all_tracks != on_any_tracks:
        message = f"{tag} policy={policy.name} but it is on some tracks and not others"
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
                    if value is None and track.has(tag):
                        ctx.console.print(f"removing {tag} from {track.filename}")
                        tagger.set_basic_tags(path, [(tag, None)])
                        changed = True
                    if value is not None and (not track.has(tag) or track.get(tag) != [value]):
                        ctx.console.print(f"setting {tag} on {track.filename}")
                        tagger.set_basic_tags(path, [(tag, value)])
                        changed = True
                return changed

            options = [] if policy == Policy.ALWAYS else [f"{OPTION_REMOVE_TAG} {tag}"]
            option_automatic_index = 0 if len(options) == 1 else None
            if policy == Policy.NEVER:
                option_free_text = False
            table = (["track", "filename"], [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)])
            fixer = Fixer(lambda option: _fix(option), options, option_free_text, option_automatic_index, table)
        else:
            fixer = None

        return CheckResult(message, fixer)

    return None
