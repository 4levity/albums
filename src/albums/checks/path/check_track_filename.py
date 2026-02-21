from copy import copy
from os import rename
from pathlib import Path
from typing import Any, List, Sequence, Tuple

from pathvalidate import sanitize_filename
from rich.console import RenderableType

from ...types import Album, CheckResult, Fixer, ProblemCategory, Track
from ..base_check import Check


class CheckTrackFilename(Check):
    name = "track-filename"
    default_config = {"enabled": True, "track_number_suffix": " ", "replace_invalid": "", "replace_slash": "-"}
    must_pass_checks = {"album-artist", "artist-tag", "track-numbering", "track-title", "zero-pad-numbers"}

    def init(self, check_config: dict[str, Any]):
        self.track_number_suffix = str(check_config.get("track_number_suffix", CheckTrackFilename.default_config["track_number_suffix"]))
        self.replace_invalid = str(check_config.get("replace_invalid", CheckTrackFilename.default_config["replace_invalid"]))
        self.replace_slash = str(check_config.get("replace_slash", CheckTrackFilename.default_config["replace_slash"]))

    def check(self, album: Album):
        generated_filenames = [self._generate_filename(track) for track in album.tracks]
        if len(set(str.lower(filename) for filename in generated_filenames)) != len(generated_filenames):
            # because of earlier checks the tracks should typically have unique track number and title by now so this is an error
            return CheckResult(ProblemCategory.FILENAMES, "unable to generate unique filenames using tags on these tracks")
        if any(filename.startswith(".") for filename in generated_filenames):
            return CheckResult(
                ProblemCategory.FILENAMES, "cannot generate filenames that start with . character (maybe a track has no track number or title)"
            )
        if any(track.filename != generated_filenames[ix] for ix, track in enumerate(album.tracks)):
            options = [">> Use generated filenames"]
            option_automatic_index = 0
            headers = ["Current Filename", "Disc#", "Track#", "Title Tag", "Proposed Filename"]
            table: Tuple[Sequence[str], Sequence[List[RenderableType]]] = (headers, [self._table_row(track) for track in album.tracks])
            return CheckResult(
                ProblemCategory.FILENAMES,
                "track filenames do not match configured pattern",
                Fixer(lambda _: self._fix_use_generated(album), options, False, option_automatic_index, table),
            )

    def _table_row(self, track: Track) -> List[RenderableType]:
        title_tags = ", ".join(track.tags.get("title", ["[bold italic]none[/bold italic]"]))
        discnum = track.tags.get("discnumber", ["[bold italic]none[/bold italic]"])[0]
        tracknum = track.tags.get("tracknumber", ["[bold italic]none[/bold italic]"])[0]
        new_filename = self._generate_filename(track)
        return [
            track.filename,
            discnum,
            tracknum,
            title_tags,
            new_filename if new_filename != track.filename else "[bold italic]no change[/bold italic]",
        ]

    def _generate_filename(self, track: Track):
        tracktag = track.tags.get("tracknumber")
        tracknum = tracktag[0] if tracktag else None
        if tracknum:
            disctag = track.tags.get("discnumber")
            discnum = disctag[0] if disctag else None
            if discnum:
                filename = f"{discnum}-{tracknum}{self.track_number_suffix}"
            else:
                filename = f"{tracknum}{self.track_number_suffix}"
        else:
            filename = ""

        title = ", ".join(track.tags.get("title", [f"Track {tracknum}" if tracknum else ""]))
        if "artist" in track.tags and "albumartist" in track.tags and track.tags["artist"] != track.tags["albumartist"]:
            filename += f"{', '.join(track.tags['artist'])} - {title}"
        else:
            filename += title

        filename = filename.replace("/", self.replace_slash)
        filename = sanitize_filename(
            filename + Path(track.filename).suffix, replacement_text=self.replace_invalid, platform=self.ctx.config.path_compatibility
        )
        return filename

    def _fix_use_generated(self, album: Album):
        album_path = self.ctx.config.library / album.path

        tracks_to_rename = [copy(track) for track in album.tracks if self._generate_filename(track) != track.filename]
        new_filenames = [self._generate_filename(track) for track in tracks_to_rename]

        old_filenames_lower = {str.lower(track.filename) for track in tracks_to_rename}
        new_filenames_lower = {str.lower(filename) for filename in new_filenames}
        if new_filenames_lower.intersection(old_filenames_lower):
            # additional rename if tracks are swapping filenames
            self.ctx.console.print("A new filename is the same as a different track's old filename")
            for track in tracks_to_rename:
                num = 0
                while (temp := (album_path / track.filename).with_suffix(f".{num}")) and temp.exists():
                    num += 1
                original_filename = track.filename
                track.filename = temp.name
                self.ctx.console.print(f"Temporarily renaming {original_filename} to {track.filename}")
                rename(album_path / original_filename, album_path / track.filename)

        for ix, track in enumerate(tracks_to_rename):
            new_filename = new_filenames[ix]
            self.ctx.console.print(f"Renaming {track.filename} to {new_filename}")
            rename(album_path / track.filename, album_path / new_filename)

        return True
