from collections import defaultdict
from enum import Enum, auto
from typing import Final

from rich.markup import escape

from albums.app import Context
from albums.entities import Album
from albums.tagger import AlbumTagger, BasicField

from .check_types import CheckResult, Fixer, FixResult
from .helpers import describe_track_number, ordered_tracks

OPTION_REMOVE_FIELD: Final = ">> Remove field"


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
    field: BasicField,
    required_field: BasicField | None,
    single_value_for_album: bool = False,
) -> CheckResult | None:
    if policy == Policy.NEVER and single_value_for_album:
        raise ValueError("check_policy: Policy.NEVER cannot be used with single_value_for_album")
    on_all_tracks = all(t.has(field) for t in album.tracks)
    on_any_tracks = any(t.has(field) for t in album.tracks)
    field_without_required = required_field is not None and any(t.has(field) and not t.has(required_field) for t in album.tracks)

    if (
        (policy == Policy.ALWAYS and on_all_tracks)
        or (policy == Policy.NEVER and not on_any_tracks)
        or (policy == Policy.CONSISTENT and on_all_tracks == on_any_tracks)
    ):
        return None

    can_set_field_on_all_tracks = required_field is None or all(track.has(required_field) for track in album.tracks)
    if policy != Policy.NEVER and can_set_field_on_all_tracks:
        value_count: defaultdict[str, int] = defaultdict(int)
        for track in album.tracks:
            for value in track.get(field, default=[]):
                value_count[value] += 1
        options = [v for v, _ct in sorted(value_count.items(), key=lambda vc: vc[1], reverse=True)]
    else:
        options = []
    value_options_count = len(options)
    if policy != Policy.ALWAYS:
        options.append(f"{OPTION_REMOVE_FIELD} {field}")

    if options:
        option_automatic_index = 0 if (value_options_count == 1 or len(options) == 1) else None
        table = (
            ["track", "filename", field.value],
            [[describe_track_number(track), escape(track.filename), "/".join(track.get(field, [""]))] for track in ordered_tracks(album)],
        )
        fixer = Fixer(
            lambda option: _fix(ctx, tagger, album, field, option),
            options,
            single_value_for_album and can_set_field_on_all_tracks,
            option_automatic_index,
            table,
        )
    else:
        fixer = None

    if field_without_required:
        return CheckResult(f"{field} appears on tracks without {required_field}", fixer)
    if policy == Policy.ALWAYS and not on_all_tracks:
        return CheckResult(f"{field} policy={policy.name} but it is not on all tracks", fixer)
    elif policy == Policy.NEVER and on_any_tracks:
        return CheckResult(f"{field} policy={policy.name} but it appears on tracks", fixer)
    elif policy == Policy.CONSISTENT and on_all_tracks != on_any_tracks:
        return CheckResult(f"{field} policy={policy.name} but it is on some tracks and not others", fixer)
    raise RuntimeError(f"internal error! field={field.value}, policy={policy.name}, on_all_tracks={on_all_tracks}, on_any_tracks={on_any_tracks}")


def _fix(ctx: Context, tagger: AlbumTagger, album: Album, field: BasicField, option: str) -> FixResult:
    if option.startswith(OPTION_REMOVE_FIELD):
        value = None
    else:
        value = option
    changed = False
    for track in sorted(album.tracks):
        path = ctx.config.library / album.path / track.filename
        if value is None and track.has(field):
            ctx.console.print(f"removing {field} from {escape(track.filename)}", highlight=False)
            tagger.set_basic_fields(path, [(field, None)])
            changed = True
        if value is not None and (not track.has(field) or track.get(field) != (value,)):
            ctx.console.print(f"setting {field} on {escape(track.filename)}", highlight=False)
            tagger.set_basic_fields(path, [(field, value)])
            changed = True
    return FixResult.of(changed)
