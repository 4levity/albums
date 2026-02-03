import logging
from pathlib import Path
from rich.markup import escape
from typing import Any

from .. import app
from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, Track
from .base_check import ProblemCategory, Check, CheckResult, Fixer
from .helpers import describe_track_number, get_tracks_by_disc, ordered_tracks


logger = logging.getLogger(__name__)


class TrackNumberFixer(Fixer):
    def __init__(self, ctx: app.Context, album: Album):
        # sort by discnumber/tracknumber tag if all tracks have one
        has_discnumber = all(len(track.tags.get("discnumber", [])) == 1 for track in album.tracks)
        tracks = [
            [describe_track_number(track), escape(track.filename), f"{'' if has_discnumber else (index + 1)}"]
            for (index, track) in enumerate(ordered_tracks(album))
        ]
        table = (["track", "filename", "proposed track #"], tracks)
        super(TrackNumberFixer, self).__init__(lambda option: self._fix(ctx, album, option), ["no valid options yet"], False, None, table)

    def _fix(self, ctx: app.Context, album: Album, option: str) -> bool:
        raise NotImplementedError("TrackNumberFixer fix not implemented")


class TrackTotalFixer(Fixer):
    OPTION_USE_TRACK_COUNT = ">> Set tracktotal to number of tracks"
    OPTION_USE_MAX = ">> Set tracktotal to maximum value seen"

    def __init__(self, ctx: app.Context, album: Album, discnumber: int | None):
        self.tracks: list[Track] = []
        for track in ordered_tracks(album):
            if discnumber is None or (track.tags.get("discnumber", [""])[0].isdecimal() and int(track.tags["discnumber"][0]) == discnumber):
                self.tracks.append(track)

        self.max_tracktotal = max(
            (
                int(track.tags["tracktotal"][0])
                for track in self.tracks
                if track.tags.get("tracktotal", [""])[0].isdecimal() and (discnumber is None or int(track.tags["discnumber"][0]) == discnumber)
            ),
            default=None,
        )
        discnumber_notice = {f" on disc {discnumber}"} if discnumber is not None else ""
        options = [f"{TrackTotalFixer.OPTION_USE_TRACK_COUNT}: {len(self.tracks)}{discnumber_notice}"]
        if self.max_tracktotal:
            options.append(f"{TrackTotalFixer.OPTION_USE_MAX}: {self.max_tracktotal}{discnumber_notice}")

        tracks = [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)]
        table = (["track", "filename"], tracks)
        # TODO highlight tracks we are fixing e.g. only disc 1 or disc 2

        super(TrackTotalFixer, self).__init__(
            lambda option: self._fix(ctx, album, option),
            options,
            True,
            None,
            table,
            f"select option to apply to {len(self.tracks)} tracks{discnumber_notice}",
        )

    def _fix(self, ctx: app.Context, album: Album, option: str | None):
        if option is None:
            new_tracktotal = None
        elif option.startswith(TrackTotalFixer.OPTION_USE_TRACK_COUNT):
            new_tracktotal = len(self.tracks)
        elif option.startswith(TrackTotalFixer.OPTION_USE_MAX):
            new_tracktotal = self.max_tracktotal
        else:
            logger.error(f"invalid option for fix_interactive: {option}")
            return False

        changed = False
        for track in self.tracks:
            path = (ctx.library_root if ctx.library_root else Path(".")) / album.path / track.filename
            if new_tracktotal is None and "tracktotal" in track.tags:
                ctx.console.print(f"removing tracktotal from {track.filename}")
                changed = True
            elif new_tracktotal is not None and track.tags.get("tracktotal", []) != [str(new_tracktotal)]:
                ctx.console.print(f"setting tracktotal on {track.filename}")
                changed = True
            if changed:
                set_basic_tags(path, [("tracktotal", new_tracktotal if new_tracktotal is None else str(new_tracktotal))])
        return changed


class CheckTrackNumber(Check):
    name = "track_number"
    default_config = {"enabled": True, "ignore_folders": ["misc"], "discs_in_separate_folders": True}
    must_pass_checks = {"invalid_track_or_disc_number"}

    def init(self, check_config: dict[str, Any]):
        ignore_folders: list[Any] = check_config.get("ignore_folders", CheckTrackNumber.default_config["ignore_folders"])
        if not isinstance(ignore_folders, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(f, str) or f == "" for f in ignore_folders
        ):
            logger.warning(f'album_tag.ignore_folders must be a list of folders, ignoring value "{ignore_folders}"')
            ignore_folders = []
        self.ignore_folders = list(str(folder) for folder in ignore_folders)
        self.discs_in_separate_folders = check_config.get("discs_in_separate_folders", CheckTrackNumber.default_config["discs_in_separate_folders"])

    def check(self, album: Album):
        folder_str = Path(album.path).name
        if folder_str in self.ignore_folders:
            return None

        if not album_is_basic_taggable(album):
            return None  # this check works for tracks with "tracknumber" tag

        tracks_by_disc = get_tracks_by_disc(album.tracks)
        if not tracks_by_disc:
            return CheckResult(ProblemCategory.TAGS, "couldn't arrange tracks by disc - invalid_track_or_disc_number check must pass first")

        # now, all tracknumber/tracktotal/discnumber/disctotal tags are guaranteed single-valued and numeric
        # TODO ensure check_disc_numbering has passed, we need check deps

        for disc_number in tracks_by_disc.keys():
            tracks = tracks_by_disc[disc_number]
            expect_track_total = len(tracks)  # will set to tracktotal if higher value is seen
            actual_track_numbers: set[int] = set()
            track_total_counts: dict[int, int] = {}
            duplicate_tracks: list[int] = []
            for track in tracks:
                if "tracknumber" in track.tags:
                    tracknumber = int(track.tags["tracknumber"][0])
                    if tracknumber in actual_track_numbers:
                        duplicate_tracks.append(tracknumber)
                    actual_track_numbers.add(tracknumber)
                if "tracktotal" in track.tags:
                    tracktotal = int(track.tags["tracktotal"][0])
                    track_total_counts[tracktotal] = track_total_counts.get(tracktotal, 0) + 1
                    if tracktotal > expect_track_total:
                        expect_track_total = tracktotal

            on_disc_message = f" on disc {disc_number}" if disc_number else ""
            if len(track_total_counts) > 1:
                return CheckResult(
                    ProblemCategory.TAGS,
                    f"some tracks have different tracktotal values{on_disc_message} - {list(track_total_counts.keys())}",
                    TrackTotalFixer(self.ctx, album, int(disc_number) if disc_number else None),
                )
            elif len(track_total_counts) == 1:
                (tracktotal, tracktotal_tagged_count) = list(track_total_counts.items())[0]
                if tracktotal == len(tracks) and tracktotal != tracktotal_tagged_count:
                    # tracktotal matches the number of tracks, but not all tracks have tracktotal tag
                    return CheckResult(
                        ProblemCategory.TAGS,
                        f"tracktotal = {tracktotal} is not set on all tracks{on_disc_message}",
                        TrackTotalFixer(self.ctx, album, int(disc_number) if disc_number else None),
                    )
                elif tracktotal_tagged_count != len(tracks):  # hmm needs clarification
                    return CheckResult(
                        ProblemCategory.TAGS,
                        f"tracktotal = {tracktotal} is set on {tracktotal_tagged_count}/{len(tracks)} tracks{on_disc_message}",
                        TrackTotalFixer(self.ctx, album, int(disc_number) if disc_number else None),
                    )

            expected_track_numbers = set(range(1, expect_track_total + 1))
            missing_track_numbers = expected_track_numbers - actual_track_numbers
            unexpected_track_numbers = actual_track_numbers - expected_track_numbers
            if actual_track_numbers > expected_track_numbers:
                return CheckResult(
                    ProblemCategory.TAGS,
                    f"unexpected track numbers{on_disc_message} {unexpected_track_numbers}",
                    TrackNumberFixer(self.ctx, album),
                )
            elif len(missing_track_numbers) > 0:
                if duplicate_tracks:
                    return CheckResult(
                        ProblemCategory.TAGS,
                        f"duplicate track numbers{on_disc_message}: {duplicate_tracks}",
                        TrackNumberFixer(self.ctx, album),
                    )
                if len(actual_track_numbers) == len(tracks):
                    # if all tracks have a unique track number tag and there are no unexpected track numbers but there are missing track numbers,
                    # then it looks like the album is incomplete.
                    return CheckResult(
                        ProblemCategory.OTHER,
                        f"tracks missing from album{on_disc_message} {missing_track_numbers}",
                        TrackNumberFixer(self.ctx, album),
                    )
                return CheckResult(
                    ProblemCategory.TAGS,
                    f"missing track numbers or tags{on_disc_message} {missing_track_numbers}",
                    TrackNumberFixer(self.ctx, album),
                )

        return None
