from collections import defaultdict
from enum import Enum, auto
from typing import Final

from rich.markup import escape

from ..app import Context
from ..tagger.folder import AlbumTagger
from ..tagger.types import BasicTag
from ..types import Album, CheckResult, Fixer, FixResult
from .helpers import describe_track_number, ordered_tracks

OPTION_REMOVE_TAG: Final = ">> Remove tag"


class Policy(Enum):
    CONSISTENT = auto()
    ALWAYS = auto()
    NEVER = auto()

    @classmethod
    def from_str(cls, selection: str):
        for policy in cls:
            if str.lower(policy.name) == str.lower(selection):
                return policy
        raise ValueError(f'invalid policy "{selection}"')


def check_policy(
    ctx: Context,
    tagger: AlbumTagger,
    album: Album,
    policy: Policy,
    tag: BasicTag,
    required_tag: BasicTag | None,
    single_value_for_album: bool = False,
) -> CheckResult | None:
    if policy == Policy.NEVER and single_value_for_album:
        raise ValueError("check_policy: Policy.NEVER cannot be used with single_value_for_album")
    on_all_tracks = all(t.has(tag) for t in album.tracks)
    on_any_tracks = any(t.has(tag) for t in album.tracks)
    tag_without_required = required_tag is not None and any(t.has(tag) and not t.has(required_tag) for t in album.tracks)

    if (
        (policy == Policy.ALWAYS and on_all_tracks)
        or (policy == Policy.NEVER and not on_any_tracks)
        or (policy == Policy.CONSISTENT and on_all_tracks == on_any_tracks)
    ):
        return None

    can_set_tag_on_all_tracks = required_tag is None or all(track.has(required_tag) for track in album.tracks)
    if policy != Policy.NEVER and can_set_tag_on_all_tracks:
        value_count: defaultdict[str, int] = defaultdict(int)
        for track in album.tracks:
            for value in track.get(tag, default=[]):
                value_count[value] += 1
        options = [v for v, _ct in sorted(value_count.items(), key=lambda vc: vc[1], reverse=True)]
    else:
        options = []
    if policy != Policy.ALWAYS:
        options.append(f"{OPTION_REMOVE_TAG} {tag}")

    if options:
        option_automatic_index = 0 if len(options) == 1 else None
        table = (
            ["track", "filename", tag.value],
            [[describe_track_number(track), escape(track.filename), "/".join(track.get(tag, [""]))] for track in ordered_tracks(album)],
        )
        fixer = Fixer(
            lambda option: _fix(ctx, tagger, album, tag, option),
            options,
            single_value_for_album and can_set_tag_on_all_tracks,
            option_automatic_index,
            table,
            "select a genre or other option",
        )
    else:
        fixer = None

    if tag_without_required:
        return CheckResult(f"{tag} appears on tracks without {required_tag}", fixer)
    if policy == Policy.ALWAYS and not on_all_tracks:
        return CheckResult(f"{tag} policy={policy.name} but it is not on all tracks", fixer)
    elif policy == Policy.NEVER and on_any_tracks:
        return CheckResult(f"{tag} policy={policy.name} but it appears on tracks", fixer)
    elif policy == Policy.CONSISTENT and on_all_tracks != on_any_tracks:
        return CheckResult(f"{tag} policy={policy.name} but it is on some tracks and not others", fixer)
    raise RuntimeError(f"internal error! tag={tag.value}, policy={policy.name}, on_all_tracks={on_all_tracks}, on_any_tracks={on_any_tracks}")


def _fix(ctx: Context, tagger: AlbumTagger, album: Album, tag: BasicTag, option: str) -> FixResult:
    if option.startswith(OPTION_REMOVE_TAG):
        value = None
    else:
        value = option
    changed = False
    for track in sorted(album.tracks):
        path = ctx.config.library / album.path / track.filename
        if value is None and track.has(tag):
            ctx.console.print(f"removing {tag} from {escape(track.filename)}", highlight=False)
            tagger.set_basic_tags(path, [(tag, None)])
            changed = True
        if value is not None and (not track.has(tag) or track.get(tag) != (value,)):
            ctx.console.print(f"setting {tag} on {escape(track.filename)}", highlight=False)
            tagger.set_basic_tags(path, [(tag, value)])
            changed = True
    return FixResult.of(changed)
