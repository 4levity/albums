import logging
from pathlib import Path
from typing import Any

from .. import app
from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, Track
from .base_check import ProblemCategory, Check, CheckResult, Fixer
from .helpers import describe_track_number, get_tracks_by_disc, ordered_tracks


logger = logging.getLogger(__name__)


class DiscNumberFixer(Fixer):
    OPTION_REMOVE_DT = ">> Remove disctotal tag from all tracks"
    OPTION_REMOVE_DN_AND_DT = ">> Remove discnumber AND disctotal tag from all tracks"
    # TODO more fixer options e.g. re-number from filenames

    def __init__(self, ctx: app.Context, album: Album, option_remove_disctotal: bool, option_remove_discnumber_and_disctotal: bool):
        tracks = [[describe_track_number(track), track.filename] for track in ordered_tracks(album)]
        table = (["disc/track", "filename"], tracks)
        options: list[str] = []
        if option_remove_disctotal:
            options.append(DiscNumberFixer.OPTION_REMOVE_DT)
        if option_remove_discnumber_and_disctotal:
            options.append(DiscNumberFixer.OPTION_REMOVE_DN_AND_DT)

        super(DiscNumberFixer, self).__init__(lambda option: self._fix(ctx, album, option), options, False, None, table)

    def get_interactive_prompt(self):
        return self.prompt

    def _fix(self, ctx: app.Context, album: Album, option: str | None) -> bool:
        if option not in [DiscNumberFixer.OPTION_REMOVE_DN_AND_DT, DiscNumberFixer.OPTION_REMOVE_DT]:
            raise ValueError(f"DiscNumberFixer invalid option {option}")

        remove_discnumber = option.startswith(DiscNumberFixer.OPTION_REMOVE_DN_AND_DT)
        for track in album.tracks:
            path = (ctx.library_root if ctx.library_root else Path(".")) / album.path / track.filename
            if "disctotal" in track.tags or (remove_discnumber and "discnumber" in track.tags):
                ctx.console.print(f"removing {'discnumber and ' if remove_discnumber else ''}disctotal from {track.filename}")
                if remove_discnumber:
                    set_basic_tags(path, [("discnumber", None), ("disctotal", None)])
                else:
                    set_basic_tags(path, [("disctotal", None)])

        return True


class TrackNumberFixer(Fixer):
    def __init__(self, ctx: app.Context, album: Album):
        # sort by discnumber/tracknumber tag if all tracks have one
        has_discnumber = all(len(track.tags.get("discnumber", [])) == 1 for track in album.tracks)
        tracks = [
            [describe_track_number(track), track.filename, f"{'' if has_discnumber else (index + 1)}"]
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

        tracks = [[describe_track_number(track), track.filename] for track in ordered_tracks(album)]
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
    default_config = {"enabled": True, "ignore_folders": ["misc"], "warn_disc_per_folder": False}

    def init(self, check_config: dict[str, Any]):
        ignore_folders: list[Any] = check_config.get("ignore_folders", CheckTrackNumber.default_config["ignore_folders"])
        if not isinstance(ignore_folders, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(f, str) or f == "" for f in ignore_folders
        ):
            logger.warning(f'album_tag.ignore_folders must be a list of folders, ignoring value "{ignore_folders}"')
            ignore_folders = []
        self.ignore_folders = list(str(folder) for folder in ignore_folders)
        self.warn_disc_per_folder = check_config.get("warn_disc_per_folder", CheckTrackNumber.default_config["warn_disc_per_folder"])

    def check(self, album: Album):
        folder_str = Path(album.path).name
        if folder_str in self.ignore_folders:
            return None

        if not album_is_basic_taggable(album):
            return None  # this check works for tracks with "tracknumber" tag

        tracks_by_disc = get_tracks_by_disc(album.tracks)
        if not tracks_by_disc:
            return CheckResult(
                ProblemCategory.TAGS, "couldn't arrange tracks by disc - disc_in_track_number and invalid_track_or_disc_number checks must pass first"
            )

        # now, all tracknumber/tracktotal/discnumber/disctotal tags are guaranteed single-valued and numeric

        # first we need to eliminate issues with discnumber
        all_disc_numbers = set((int(track.tags["discnumber"][0]) if "discnumber" in track.tags else 0) for track in album.tracks)
        all_disc_totals = set((int(track.tags["disctotal"][0]) if "disctotal" in track.tags else 0) for track in album.tracks)

        tag_issues: set[str] = set()
        option_remove_discnumber_and_disctotal = False
        option_remove_disctotal = False
        if 0 in tracks_by_disc and len(tracks_by_disc) == 1:
            # no tracks have a disc number
            if len(list(filter(None, all_disc_totals))) > 0:
                tag_issues.add("disctotal tags present without discnumber tags")
                option_remove_disctotal = True

        # has discnumber:
        elif 0 in tracks_by_disc:
            tag_issues.add("some tracks have discnumber tag and some do not")
            option_remove_discnumber_and_disctotal = True
        else:
            expect_disc_total = len(all_disc_numbers)
            expect_disc_numbers = set(range(1, expect_disc_total + 1))
            if expect_disc_total == 1 and len(all_disc_numbers) == 1:
                if self.warn_disc_per_folder:
                    tag_issues.add(f"unnecessary discnumber {list(all_disc_numbers)[0]} because there is only 1 disc")
                    option_remove_discnumber_and_disctotal = True
            elif all_disc_numbers < expect_disc_numbers:
                tag_issues.add(f"not all disc numbers from 1-{expect_disc_total} present")
            elif all_disc_numbers > expect_disc_numbers:
                tag_issues.add("unexpected disc numbers present")
        # if there are issues with discnumbers, that's the next thing to fix
        if len(tag_issues) > 0:
            return CheckResult(
                ProblemCategory.TAGS,
                f"discnumber/disctotal problems: {', '.join(tag_issues)}",
                DiscNumberFixer(self.ctx, album, option_remove_disctotal, option_remove_discnumber_and_disctotal),
            )

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

            if len(tag_issues) > 0:  # if there are non-numeric/multiple value tags, stop here
                return CheckResult(
                    ProblemCategory.TAGS,
                    f"tracknumber/tracktotal tag problems: {', '.join(tag_issues)}",
                    TrackNumberFixer(self.ctx, album),
                )

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
