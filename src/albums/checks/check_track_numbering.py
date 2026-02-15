import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, List

from rich.console import RenderableType
from rich.markup import escape

from .. import app
from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, Track
from . import total_tags
from .base_check import Check, CheckResult, Fixer, ProblemCategory
from .helpers import describe_track_number, get_tracks_by_disc, ordered_tracks, parse_filename

logger = logging.getLogger(__name__)


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
        option_automatic_index = None
        if self.max_tracktotal and len(self.tracks) != self.max_tracktotal:
            options.append(f"{TrackTotalFixer.OPTION_USE_MAX}: {self.max_tracktotal}{discnumber_notice}")
        elif not self.max_tracktotal or len(self.tracks) == self.max_tracktotal:
            option_automatic_index = 0

        tracks: List[List[RenderableType]] = [[describe_track_number(track), escape(track.filename)] for track in ordered_tracks(album)]
        table = (["track", "filename"], tracks)
        # TODO highlight tracks we are fixing e.g. only disc 1 or disc 2

        super(TrackTotalFixer, self).__init__(
            lambda option: self._fix(ctx, album, option),
            options,
            True,
            option_automatic_index,
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
            path = ctx.config.library / album.path / track.filename
            track_changed = False
            if new_tracktotal is None and "tracktotal" in track.tags:
                ctx.console.print(f"removing tracktotal from {escape(track.filename)}", highlight=False)
            elif new_tracktotal is not None and track.tags.get("tracktotal", []) != [str(new_tracktotal)]:
                ctx.console.print(f"setting tracktotal on {escape(track.filename)}", highlight=False)
                track_changed = True
            if track_changed:
                changed = True
                set_basic_tags(path, [("tracktotal", new_tracktotal if new_tracktotal is None else str(new_tracktotal))])
        return changed


class CheckTrackNumbering(Check):
    name = "track_numbering"
    default_config = {"enabled": True, "ignore_folders": ["misc"], "tracktotal_policy": "consistent"}
    must_pass_checks = {"disc_numbering"}

    def init(self, check_config: dict[str, Any]):
        ignore_folders: list[Any] = check_config.get("ignore_folders", CheckTrackNumbering.default_config["ignore_folders"])
        if not isinstance(ignore_folders, list) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(f, str) or f == "" for f in ignore_folders
        ):
            logger.warning(f'track_numbering.ignore_folders must be a list of folders, ignoring value "{ignore_folders}"')
            ignore_folders = []
        self.ignore_folders = list(str(folder) for folder in ignore_folders)
        self.tracktotal_policy = total_tags.Policy.from_str(str(check_config.get("tracktotal_policy", self.default_config["tracktotal_policy"])))

    def check(self, album: Album):
        folder_str = Path(album.path).name
        if folder_str in self.ignore_folders:
            return None

        if not album_is_basic_taggable(album):
            return None  # this check works for tracks with "tracknumber" tag

        tracks_by_disc = get_tracks_by_disc(album.tracks)
        if not tracks_by_disc:
            return CheckResult(ProblemCategory.TAGS, "couldn't arrange tracks by disc - disc_numbering check must pass first")
        # now, all tracknumber/tracktotal/discnumber/disctotal tags are guaranteed single-valued and numeric if present

        # apply track total policy - will offer automatic fix (remove all track totals) if policy is not "always"
        one_track_total = len(tracks_by_disc) == 1  # fix will allow manual entry if there is only one disc
        tracktotal_result = total_tags.check_policy(self.ctx, album, self.tracktotal_policy, "tracktotal", "tracknumber", one_track_total)
        if tracktotal_result:
            # TODO if policy is "always" and some tags are missing, we could ignore it and automatically fix them instead
            return tracktotal_result

        for disc_number in tracks_by_disc.keys():
            tracks = tracks_by_disc[disc_number]
            expect_track_total = 0
            actual_track_numbers: set[int] = set()
            track_total_counts: defaultdict[int, int] = defaultdict(int)
            duplicate_tracks: list[int] = []
            for track in tracks:
                if "tracknumber" in track.tags:
                    tracknumber = int(track.tags["tracknumber"][0])
                    if tracknumber in actual_track_numbers:
                        duplicate_tracks.append(tracknumber)
                    actual_track_numbers.add(tracknumber)
                if "tracktotal" in track.tags:
                    tracktotal = int(track.tags["tracktotal"][0])
                    track_total_counts[tracktotal] += 1
                    if tracktotal > expect_track_total:
                        expect_track_total = tracktotal

            if expect_track_total == 0:
                # we will expect tracks to be numbered from 1..track total
                # if there is no track total, use 1..(# of tracks) or 1..(highest track number), whichever is more tracks
                expect_track_total = max([len(tracks), *list(actual_track_numbers)])

            on_disc_message = f" on disc {disc_number}" if disc_number else ""
            if len(track_total_counts) > 1:
                return CheckResult(
                    ProblemCategory.TAGS,
                    f"some tracks have different track total values{on_disc_message} - {list(track_total_counts.keys())}",
                    TrackTotalFixer(self.ctx, album, int(disc_number) if disc_number else None),
                )

            # if there is a track total for this disc, it is in expect_track_total

            expected_track_numbers = set(range(1, expect_track_total + 1))
            missing_track_numbers = expected_track_numbers - actual_track_numbers
            unexpected_track_numbers = actual_track_numbers - expected_track_numbers
            if actual_track_numbers > expected_track_numbers:
                return CheckResult(ProblemCategory.TAGS, f"unexpected track numbers{on_disc_message} {unexpected_track_numbers}")
            elif len(missing_track_numbers) > 0:
                if duplicate_tracks:
                    return CheckResult(ProblemCategory.TAGS, f"duplicate track numbers{on_disc_message} {duplicate_tracks}")
                if len(actual_track_numbers) == len(tracks):
                    # if all tracks have a unique track number tag and there are no unexpected track numbers but there are missing track numbers,
                    # then it looks like the album is incomplete.
                    return CheckResult(ProblemCategory.TAGS, f"tracks missing from album{on_disc_message} {missing_track_numbers}")

                # TODO: we can probably offer this fixer in some other cases, also
                fixer = self._renumber_fixer(album, disc_number, tracks)
                return CheckResult(ProblemCategory.TAGS, f"missing track numbers{on_disc_message} {missing_track_numbers}", fixer)

        return None

    def _renumber_fixer(self, album: Album, disc_number: int, tracks: list[Track]) -> Fixer | None:
        new_tracknumbers: dict[str, str] = {}
        for track in tracks:
            tag_tracknumber = int(track.tags.get("tracknumber", [0])[0])
            (filename_discnumber, filename_tracknumber, _) = parse_filename(track.filename)

            if filename_discnumber and filename_discnumber != disc_number:
                return None  # track filename indicates unexpected disc number
            if not tag_tracknumber and not filename_tracknumber:
                return None  # track has no track number and there is no guess from filename
            if filename_tracknumber and tag_tracknumber != filename_tracknumber:
                new_tracknumbers[track.filename] = str(filename_tracknumber)
        if not new_tracknumbers:
            return None
        options = [f">> Automatically renumber {len(new_tracknumbers)} tracks based on filenames"]
        option_automatic_index = 0

        table: tuple[list[str], List[List[RenderableType]]] = (
            ["track", "filename", "proposed new track #"],
            [[describe_track_number(track), escape(track.filename), new_tracknumbers.get(track.filename, "")] for track in ordered_tracks(album)],
        )

        return Fixer(lambda _: self._renumber(album, new_tracknumbers), options, False, option_automatic_index, table)

    def _renumber(self, album: Album, new_tracknumbers: dict[str, str]) -> bool:
        for track in album.tracks:
            if track.filename in new_tracknumbers:
                new_tracknumber = new_tracknumbers[track.filename]
                path = self.ctx.config.library / album.path / track.filename
                self.ctx.console.print(f"setting track number {new_tracknumber} on {track.filename}")
                set_basic_tags(path, [("tracknumber", new_tracknumber)])
        return True
