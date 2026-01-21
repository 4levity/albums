import logging
from pathlib import Path
import re

from ..library.metadata import album_is_basic_taggable
from ..types import Album, Track
from .base_check import Check, CheckResult
from .normalize_tags import normalized


logger = logging.getLogger(__name__)


CHECK_NAME = "track_number"


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
            return None  # this check works for tracks with "tracknumber" and "tracktotal" tag (or normalized, see normalize)

        # if tracknumber is formatted as "1-03" with disc and track together, this isn't valid so normalize won't fix it
        disc_in_tracknumber = all(re.match("\\d+-\\d+", "|".join(track.tags.get("tracknumber", []))) for track in album.tracks)

        (tracks_by_disc, tag_issues) = _tracks_by_disc_with_issues(album.tracks, disc_in_tracknumber, warn_disc_per_folder)
        if disc_in_tracknumber:
            tag_issues.add("tracknumber tag contains disc number")

        for discnumber in tracks_by_disc.keys():
            tracks = tracks_by_disc[discnumber]
            expect_track_total = len(tracks)
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

            on_disc_message = f" on disc {discnumber}" if discnumber else ""
            if len(track_total_counts) > 1:
                tag_issues.add(f"some tracks have different tracktotal values{on_disc_message} - {list(track_total_counts.keys())}")
            elif len(track_total_counts) == 1:
                (tracktotal, track_count) = list(track_total_counts.items())[0]
                if tracktotal != track_count or track_count != len(tracks):
                    tag_issues.add(f"tracktotal = {tracktotal} is set on {track_count}/{len(tracks)} tracks{on_disc_message}")

            expected_track_numbers = set(range(1, expect_track_total + 1))
            missing_track_numbers = expected_track_numbers - actual_track_numbers
            unexpected_track_numbers = actual_track_numbers - expected_track_numbers
            if len(missing_track_numbers) > 1:
                tag_issues.add(f"missing expected track numbers{on_disc_message} {missing_track_numbers}")
            elif actual_track_numbers > expected_track_numbers:
                tag_issues.add(f"unexpected track numbers{on_disc_message} {unexpected_track_numbers}")

        if len(tag_issues) > 0:
            message = f"issues: {', '.join(tag_issues)}"
            # fixer = TrackNumberFixer(self.ctx, album, message, ... )
            return CheckResult(self.name, message)

        return None


def _tracks_by_disc_with_issues(tracks: list[Track], disc_in_tracknumber: bool, warn_disc_per_folder: bool):
    tracks_by_disc: dict[str, list[Track]] = {}
    valid_disc_numbers: set[int] = set()
    disc_totals: set[str] = set()
    tag_issues: set[str] = set()
    for track in tracks:
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
    elif len(disc_totals) > 1:
        tag_issues.add(f"multiple values for disctotal: {disc_totals}")

    if "" in tracks_by_disc and len(tracks_by_disc) == 1:
        # disctotal with no discnumber
        if len(list(filter(None, disc_totals))) > 0:
            tag_issues.add("disctotal tags present without discnumber tags")
    # has discnumber:
    elif "" in tracks_by_disc:
        tag_issues.add("some tracks have discnumber tag and some do not")
    else:
        expect_disc_total = len(valid_disc_numbers)
        expect_disc_numbers = set(range(1, expect_disc_total + 1))
        if expect_disc_total == 1 and len(valid_disc_numbers) == 1:
            if warn_disc_per_folder:
                tag_issues.add(f"unnecessary discnumber {list(valid_disc_numbers)[0]} because there is only 1 disc")
        elif valid_disc_numbers < expect_disc_numbers:
            tag_issues.add(f"not all disc numbers from 1-{expect_disc_total} present")
        elif valid_disc_numbers > expect_disc_numbers:
            tag_issues.add("unexpected disc numbers present")

    return (tracks_by_disc, tag_issues)
