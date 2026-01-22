from copy import copy
import logging
from pathlib import Path
import re

from .. import app
from ..library.metadata import album_is_basic_taggable, set_basic_tags
from ..types import Album, Track
from .base_check import Check, CheckResult
from .base_fixer import Fixer, FixerInteractivePrompt
from .normalize_tags import normalized


logger = logging.getLogger(__name__)


CHECK_NAME = "track_number"


class DiscNumberFixer(Fixer):
    OPTION_REMOVE_DISCTOTAL = ">> Remove disctotal tag from all tracks"
    OPTION_REMOVE_DISCNUMBER_AND_DISCTOTAL = ">> Remove discnumber AND disctotal tag from all tracks"
    # TODO more fixer options e.g. re-number from filenames

    def __init__(self, ctx: app.Context, album: Album, message: str, option_remove_disctotal: bool, option_remove_discnumber_and_disctotal: bool):
        super(DiscNumberFixer, self).__init__(CHECK_NAME, ctx, album, True, None, True)
        self.options = []
        if option_remove_disctotal:
            self.options.append(DiscNumberFixer.OPTION_REMOVE_DISCTOTAL)
        if option_remove_discnumber_and_disctotal:
            self.options.append(DiscNumberFixer.OPTION_REMOVE_DISCNUMBER_AND_DISCTOTAL)
        self.message = [f"*** Fixing discnumber/disctotal tags for {self.album.path}", f"ISSUE: {message}"]

    def get_interactive_prompt(self):
        tracks = [[_describe_track_number(track), track.filename] for track in _ordered_tracks(self.album)]
        return FixerInteractivePrompt(self.message, "Select an option", self.options, (["disc/track", "filename"], tracks))

    def fix_interactive(self, option):
        if option.startswith(DiscNumberFixer.OPTION_REMOVE_DISCNUMBER_AND_DISCTOTAL):
            remove_discnumber = True
        elif option.startswith(DiscNumberFixer.OPTION_REMOVE_DISCTOTAL):
            remove_discnumber = False
        else:
            raise ValueError(f"invalid option {option}")

        for track in self.album.tracks:
            path = self.ctx.library_root / self.album.path / track.filename
            tags = normalized(track.tags)
            if "disctotal" in tags or (remove_discnumber and "discnumber" in tags):
                self.ctx.console.print(f"removing {'discnumber and ' if remove_discnumber else ''}disctotal from {track.filename}")
                if remove_discnumber:
                    set_basic_tags(path, [("discnumber", None), ("disctotal", None)])
                else:
                    set_basic_tags(path, [("disctotal", None)])

        return True


class TrackNumberFixer(Fixer):
    def __init__(self, ctx: app.Context, album: Album, message: str):
        super(TrackNumberFixer, self).__init__(CHECK_NAME, ctx, album, True, None, True)
        self.message = [f"*** Fixing track/disc number tags for {self.album.path}", f"ISSUE: {message}"]
        self.question = "Which track numbering option to apply?"
        self.options = []  # with no options, user can run external tagger or ignore

    def get_interactive_prompt(self):
        # sort by discnumber/tracknumber tag if all tracks have one
        has_discnumber = all(len(track.tags.get("discnumber", [])) == 1 for track in self.album.tracks)
        if all(len(track.tags.get("tracknumber", [])) == 1 for track in self.album.tracks):
            if has_discnumber:
                ordered_tracks = sorted(self.album.tracks, key=lambda t: (t.tags["discnumber"][0], t.tags["tracknumber"][0]))
            else:
                ordered_tracks = sorted(self.album.tracks, key=lambda t: t.tags["tracknumber"][0])
        else:  # default album sort is by filename
            ordered_tracks = self.album.tracks
        tracks = [
            [_describe_track_number(track), track.filename, f"{'' if has_discnumber else (index + 1)}"]
            for (index, track) in enumerate(ordered_tracks)
        ]
        table = (["track", "filename", "proposed track #"], tracks)
        return FixerInteractivePrompt(self.message, self.question, self.options, table, False, False)

    # TODO better proposed track numbers, actual fixer!


class TrackTotalFixer(Fixer):
    OPTION_USE_TRACK_COUNT = ">> Set tracktotal to number of tracks"
    OPTION_USE_MAX = ">> Set tracktotal to maximum value seen"

    def __init__(self, ctx: app.Context, album: Album, discnumber: int | None, message: str):
        automatic = None  # TODO this can be automatic for at least some situations
        super(TrackTotalFixer, self).__init__(CHECK_NAME, ctx, album, True, automatic, True)
        self.message = [f"*** Fixing tracktotal values for {self.album.path}", f"ISSUE: {message}"]
        self.tracks = []
        for track in _ordered_tracks(self.album):
            tags = normalized(track.tags)
            if discnumber is None or (tags.get("discnumber", [""])[0].isdecimal() and int(tags["discnumber"][0]) == discnumber):
                normalized_track = copy(track)
                normalized_track.tags = tags
                self.tracks.append(normalized_track)
        self.max_tracktotal = max(
            (
                int(track.tags["tracktotal"][0])
                for track in self.tracks
                if track.tags.get("discnumber", [""])[0].isdecimal()
                and (discnumber is None or int(track.tags["discnumber"][0]) == discnumber)
                and track.tags.get("tracktotal", [""])[0].isdecimal()
            ),
            default=None,
        )
        discnumber_notice = {f" on disc {discnumber}"} if discnumber is not None else ""
        self.options = [f"{TrackTotalFixer.OPTION_USE_TRACK_COUNT}: {len(self.tracks)}{discnumber_notice}"]
        if self.max_tracktotal:
            self.options.append(f"{TrackTotalFixer.OPTION_USE_MAX}: {self.max_tracktotal}{discnumber_notice}")
        self.question = f"Which option to apply to {len(self.tracks)} tracks{discnumber_notice}?"

    def get_interactive_prompt(self):
        tracks = [[_describe_track_number(track), track.filename] for track in _ordered_tracks(self.album)]
        table = (["track", "filename"], tracks)
        # TODO highlight tracks we are fixing e.g. only disc 1 or disc 2
        return FixerInteractivePrompt(self.message, self.question, self.options, table, True, True)

    def fix_interactive(self, option):
        if option.startswith(TrackTotalFixer.OPTION_USE_TRACK_COUNT):
            new_tracktotal = len(self.tracks)
        elif option.startswith(TrackTotalFixer.OPTION_USE_MAX):
            new_tracktotal = self.max_tracktotal
        elif option is None:
            new_tracktotal = None
        else:
            logger.error(f"invalid option for fix_interactive: {option}")
            return False

        changed = False
        for track in self.tracks:
            path = self.ctx.library_root / self.album.path / track.filename
            tags = normalized(track.tags)
            if new_tracktotal is None and "tracktotal" in tags:
                self.ctx.console.print(f"removing tracktotal from {track.filename}")
                changed = True
            elif tags.get("tracktotal", []) != [str(new_tracktotal)]:
                self.ctx.console.print(f"setting tracktotal on {track.filename}")
                changed = True
            if changed:
                set_basic_tags(path, [("tracktotal", new_tracktotal if new_tracktotal is None else str(new_tracktotal))])
        return changed


class DiscInTracknumberFixer(Fixer):
    message = "track number contains disc number"

    OPTION_USE_PROPOSED = ">> Split track number automatically (proposed values)"

    def __init__(self, ctx: app.Context, album: Album):
        automatic = "split tracknumber -> discnumber/tracknumber"
        super(DiscInTracknumberFixer, self).__init__(CHECK_NAME, ctx, album, has_interactive=True, describe_automatic=automatic, enable_tagger=True)

    def get_interactive_prompt(self):
        tracks = [
            [_describe_track_number(track), track.filename, *self._proposed_disc_and_tracknumber(track)] for track in _ordered_tracks(self.album)
        ]
        table = (["track", "filename", "proposed disc#", "proposed track#"], tracks)
        options = [DiscInTracknumberFixer.OPTION_USE_PROPOSED]
        return FixerInteractivePrompt(DiscInTracknumberFixer.message, "track numbers are invalid - how do you want to fix them?", options, table)

    def fix_interactive(self, option):
        if option != DiscInTracknumberFixer.OPTION_USE_PROPOSED:
            raise ValueError(f"invalid option {option}")

        for track in self.album.tracks:
            path = self.ctx.library_root / self.album.path / track.filename
            self.ctx.console.print(f"setting discnumber and tracknumber on {track.filename}")
            (discnumber, tracknumber) = self._proposed_disc_and_tracknumber(track)
            set_basic_tags(path, [("discnumber", discnumber), ("tracknumber", tracknumber)])
        return True

    def fix_automatic(self):
        return self.fix_interactive(DiscInTracknumberFixer.OPTION_USE_PROPOSED)

    def _proposed_disc_and_tracknumber(self, track: Track):
        [discnumber, tracknumber] = track.tags["tracknumber"][0].split("-")
        return (discnumber, tracknumber)


class CheckTrackNumber(Check):
    name = CHECK_NAME
    default_config = {"enabled": True, "ignore_folders": ["misc"], "warn_disc_per_folder": False}

    def check(self, album: Album):
        ignore_folders = self.config.get("ignore_folders", CheckTrackNumber.default_config["ignore_folders"])
        warn_disc_per_folder = self.config.get("warn_disc_per_folder", CheckTrackNumber.default_config["warn_disc_per_folder"])
        folder_str = Path(album.path).name
        if folder_str in ignore_folders:
            return None

        if not album_is_basic_taggable(album):
            return None  # this check works for tracks with "tracknumber" tag

        # if tracknumber is formatted as "1-03" with disc and track together, need to fix that first
        disc_in_tracknumber = all(re.match("\\d+-\\d+", "|".join(track.tags.get("tracknumber", []))) for track in album.tracks)
        has_discnumber = any("discnumber" in track.tags for track in album.tracks)
        if disc_in_tracknumber and not has_discnumber:
            return CheckResult(self.name, DiscInTracknumberFixer.message, DiscInTracknumberFixer(self.ctx, album))

        # (tracks_by_disc, tag_issues) = _tracks_by_disc_with_issues(album.tracks, disc_in_tracknumber, warn_disc_per_folder)

        tracks_by_disc: dict[str, list[Track]] = {}
        valid_disc_numbers: set[int] = set()
        disc_totals: set[str] = set()
        tag_issues: set[str] = set()
        option_remove_discnumber_and_disctotal = False
        option_remove_disctotal = False
        for track in album.tracks:
            normalized_tags = normalized(track.tags)  # will split a discnumber like "2/10" into discnumber="2" disctotal="10"
            discnumbers = []
            if disc_in_tracknumber and "tracknumber" in normalized_tags and len(normalized_tags["tracknumber"]) == 1:
                discnumber = normalized_tags["tracknumber"][0].split("-")[0]
                discnumbers.append(discnumber)

            if "discnumber" in normalized_tags:
                discnumbers.extend(normalized_tags["discnumber"])
                if not all(tn.isdecimal() for tn in discnumbers):
                    tag_issues.add("non-numeric discnumber")
                elif len(discnumbers) > 1:
                    tag_issues.add("multiple values for discnumber")
                else:
                    valid_disc_numbers.add(int(discnumbers[0]))
                discnumber = discnumbers[0]
            elif not disc_in_tracknumber:
                discnumber = ""

            if discnumber in tracks_by_disc:
                tracks_by_disc[discnumber].append(track)
            else:
                tracks_by_disc[discnumber] = [track]

            if "disctotal" in normalized_tags:
                if not all(dt.isdecimal() for dt in normalized_tags["disctotal"]):
                    tag_issues.add("non-numeric disctotal")
                elif len(normalized_tags["disctotal"]) > 1:
                    tag_issues.add("multiple tag values for disctotal")
                for dt in normalized_tags["disctotal"]:
                    disc_totals.add(int(dt))
            else:
                disc_totals.add("")

        if "" in disc_totals and len(disc_totals) == 2:
            tag_issues.add("some tracks have disctotal tag and some do not")
            option_remove_disctotal = True
        elif len(disc_totals) > 1:
            tag_issues.add(f"multiple values for disctotal: {disc_totals}")
            option_remove_disctotal = True

        if "" in tracks_by_disc and len(tracks_by_disc) == 1:
            # disctotal with no discnumber
            if len(list(filter(None, disc_totals))) > 0:
                tag_issues.add("disctotal tags present without discnumber tags")
                option_remove_disctotal = True
        # has discnumber:
        elif "" in tracks_by_disc:
            tag_issues.add("some tracks have discnumber tag and some do not")
            option_remove_discnumber_and_disctotal = True
        else:
            expect_disc_total = len(valid_disc_numbers)
            expect_disc_numbers = set(range(1, expect_disc_total + 1))
            if expect_disc_total == 1 and len(valid_disc_numbers) == 1:
                if warn_disc_per_folder:
                    tag_issues.add(f"unnecessary discnumber {list(valid_disc_numbers)[0]} because there is only 1 disc")
                    option_remove_discnumber_and_disctotal = True
            elif valid_disc_numbers < expect_disc_numbers:
                tag_issues.add(f"not all disc numbers from 1-{expect_disc_total} present")
            elif valid_disc_numbers > expect_disc_numbers:
                tag_issues.add("unexpected disc numbers present")
        # if there are issues with discnumbers, that's the next thing to fix
        if len(tag_issues) > 0:
            message = f"discnumber/disctotal problems: {', '.join(tag_issues)}"
            return CheckResult(
                self.name, message, DiscNumberFixer(self.ctx, album, message, option_remove_disctotal, option_remove_discnumber_and_disctotal)
            )

        fixer: Fixer | None = None
        for discnumber in tracks_by_disc.keys():
            tracks = tracks_by_disc[discnumber]
            expect_track_total = len(tracks)  # will set to tracktotal if higher value is seen
            actual_track_numbers: set[int] = set()
            track_total_counts: dict[int, int] = {}
            for track in tracks:
                normalized_tags = normalized(track.tags)  # will split a tracknumber like "2/10" into tracknumber="2" tracktotal="10"
                if "tracknumber" in normalized_tags:
                    if not all(tn.isdecimal() for tn in normalized_tags["tracknumber"]) and not disc_in_tracknumber:
                        tag_issues.add("non-numeric tracknumber")
                    elif len(normalized_tags["tracknumber"]) > 1:
                        tag_issues.add("multiple tag values for tracknumber")
                    elif disc_in_tracknumber:
                        actual_track_numbers.add(int(normalized_tags["tracknumber"][0].split("-")[1]))
                    else:
                        actual_track_numbers.add(int(normalized_tags["tracknumber"][0]))
                if "tracktotal" in normalized_tags:
                    if not all(tt.isdecimal() for tt in normalized_tags["tracktotal"]):
                        tag_issues.add("non-numeric tracktotal")
                    elif len(normalized_tags["tracktotal"]) > 1:
                        tag_issues.add("multiple tag values for tracktotal")
                    else:
                        tracktotal = int(normalized_tags["tracktotal"][0])
                        track_total_counts[tracktotal] = track_total_counts.get(tracktotal, 0) + 1
                        if tracktotal > expect_track_total:
                            expect_track_total = tracktotal

            on_disc_message = f" on disc {discnumber}" if discnumber else ""
            if len(track_total_counts) > 1:
                tag_issues.add(f"some tracks have different tracktotal values{on_disc_message} - {list(track_total_counts.keys())}")
            elif len(track_total_counts) == 1:
                (tracktotal, tracktotal_tagged_count) = list(track_total_counts.items())[0]
                if tracktotal == len(tracks) and tracktotal != tracktotal_tagged_count:
                    # tracktotal matches the number of tracks, but not all tracks have tracktotal tag
                    message = f"tracktotal = {tracktotal} is not set on all tracks{on_disc_message}"
                    if len(tag_issues) == 0:
                        # TODO smarter decision about which fixer to present when there are multiple issues
                        fixer = TrackTotalFixer(self.ctx, album, int(discnumber) if discnumber else None, message)
                    tag_issues.add(message)
                elif tracktotal_tagged_count != len(tracks):
                    message = f"tracktotal = {tracktotal} is set on {tracktotal_tagged_count}/{len(tracks)} tracks{on_disc_message}"
                    tag_issues.add(message)
                    # TODO detect when album is probably missing tracks based on tracktotal
                    fixer = TrackTotalFixer(self.ctx, album, int(discnumber) if discnumber else None, message)

            expected_track_numbers = set(range(1, expect_track_total + 1))
            missing_track_numbers = expected_track_numbers - actual_track_numbers
            unexpected_track_numbers = actual_track_numbers - expected_track_numbers
            if actual_track_numbers > expected_track_numbers:
                tag_issues.add(f"unexpected track numbers{on_disc_message} {unexpected_track_numbers}")
            elif len(missing_track_numbers) > 1:
                if len(actual_track_numbers) == len(tracks):
                    # if all tracks have a unique track number tag but there are missing track numbers, maybe album is incomplete
                    message = f"tracks missing from album{on_disc_message} {missing_track_numbers}"
                else:
                    # TODO: report specifically on duplicate track numbers
                    message = f"missing track numbers or tags{on_disc_message} {missing_track_numbers}"
                    fixer = TrackNumberFixer(self.ctx, album, message)
                tag_issues.add(message)

        if len(tag_issues) > 0:
            message = f"issues: {', '.join(tag_issues)}"
            return CheckResult(self.name, message, fixer)

        return None


def _ordered_tracks(album: Album):
    # sort by discnumber/tracknumber tag if all tracks have one
    has_discnumber = all(len(track.tags.get("discnumber", [])) == 1 for track in album.tracks)
    if all(len(track.tags.get("tracknumber", [])) == 1 for track in album.tracks):
        if has_discnumber:
            return sorted(album.tracks, key=lambda t: (t.tags["discnumber"][0], t.tags["tracknumber"][0]))
        else:
            return sorted(album.tracks, key=lambda t: t.tags["tracknumber"][0])
    else:  # default album sort is by filename
        return album.tracks


def _describe_track_number(track: Track):
    tags = normalized(track.tags)

    if "discnumber" in tags or "disctotal" in tags:
        s = f"(disc {tags.get('discnumber', ['<no disc>'])[0]}{('/' + tags['disctotal'][0]) if 'disctotal' in tags else ''}) "
    else:
        s = ""

    s += f"{tags.get('tracknumber', ['<no track>'])[0]}{('/' + tags['tracktotal'][0]) if 'tracktotal' in tags else ''}"
    return s
