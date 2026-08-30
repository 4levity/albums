from os import rename
from pathlib import Path
from string import Template
from typing import Any, Literal, Sequence

from pathvalidate import sanitize_filename
from rich.console import RenderableType
from rich.markup import escape

from albums.checks.base_check import Check
from albums.checks.check_types import CheckResult, Fixer, FixResult
from albums.checks.numbering.check_zero_pad_numbers import CheckZeroPadNumbers, ZeroPadPolicy, apply_pad_policy
from albums.entities import Album, Track
from albums.tagger import BasicField, Cap


class CheckTrackFilename(Check):
    name = "track-filename"
    default_config = {"enabled": True, "format": "$track_auto $title_auto", "join_multiple": ", "}
    must_pass_checks = {"album-artist", "artist", "track-numbering", "track-title"}

    def init(self, check_config: dict[str, Any]):
        self.format = Template(check_config.get("format", self.default_config["format"]))
        for identifier in self.format.get_identifiers():
            if identifier not in {"tracknumber", "discnumber", "track_auto", "title", "artist", "title_auto"}:
                raise ValueError(f"invalid substitution '{identifier}' in track-filename.format")
        self.join_multiple = str(check_config.get("join_multiple", self.default_config["join_multiple"]))

    def check(self, album: Album):
        generated_filenames = [self._generate_filename(album, track) for track in sorted(album.tracks)]
        generated_filenames_lower: set[str] = set()
        for ix, filename in enumerate(generated_filenames):
            filename_lower = str.lower(filename)
            if filename_lower in generated_filenames_lower:
                # because of earlier checks the tracks should typically have unique track number and title by now so this is an error
                return CheckResult(f"unable to generate unique filenames, example conflict: {album.tracks[ix].filename} -> {filename_lower}")
            generated_filenames_lower.add(filename_lower)
        if any(filename.startswith(".") for filename in generated_filenames):
            return CheckResult("cannot generate filenames that start with . character (maybe a track has no track number or title)")
        if any(track.filename != generated_filenames[ix] for ix, track in enumerate(sorted(album.tracks))):
            options = [">> Use generated filenames"]
            option_automatic_index = 0
            headers = ["Current Filename", "Disc#", "Track#", "Title", "Proposed Filename"]
            table = (headers, [self._table_row(album, track) for track in sorted(album.tracks)])
            return CheckResult(
                "track filenames do not match configured pattern",
                Fixer(lambda _: self._fix_use_generated(album), options, False, option_automatic_index, table),
            )

    def _table_row(self, album: Album, track: Track) -> Sequence[RenderableType]:
        title_fields = ", ".join(track.get(BasicField.TITLE, default=["[bold italic]none[/bold italic]"]))
        discnum = track.get(BasicField.DISCNUMBER, default=["[bold italic]none[/bold italic]"])[0]
        tracknum = track.get(BasicField.TRACKNUMBER, default=["[bold italic]none[/bold italic]"])[0]
        new_filename = self._generate_filename(album, track)
        return [
            escape(track.filename),
            discnum,
            tracknum,
            title_fields,
            new_filename if new_filename != track.filename else "[bold italic]no change[/bold italic]",
        ]

    def _generate_filename(self, album: Album, track: Track):
        track_field = track.get(BasicField.TRACKNUMBER, default=None)
        disc_field = track.get(BasicField.DISCNUMBER, default=None)
        tracknumber = track_field[0] if track_field else ""
        discnumber = disc_field[0] if disc_field else ""

        # for padding on m4a files
        track_count = int(track.get(BasicField.TRACKTOTAL, default=["0"])[0]) or len(album.tracks)
        disc_count = int(track.get(BasicField.DISCTOTAL, default=["0"])[0]) or 9

        already_formatted = self.tagger.get(album.path).supports(track.filename, Cap.FORMATTED_TRACK_NUMBER)
        discnumber_pad = discnumber if already_formatted else self._pad("discnumber", discnumber, disc_count)
        tracknumber_pad = tracknumber if already_formatted else self._pad("tracknumber", tracknumber, track_count)
        if tracknumber_pad:
            track_auto = f"{discnumber_pad}-{tracknumber_pad}" if discnumber_pad else f"{tracknumber_pad}"
        else:
            track_auto = ""

        title = self.join_multiple.join(track.get(BasicField.TITLE, default=[f"Track {tracknumber}" if tracknumber else ""]))
        artist = self.join_multiple.join(track.get(BasicField.ARTIST, default=[""]))

        if track.has(BasicField.ARTIST) and track.has(BasicField.ALBUMARTIST) and track.get(BasicField.ARTIST) != track.get(BasicField.ALBUMARTIST):
            title_auto = f"{artist} - {title}"
        else:
            title_auto = title

        filename = self.format.safe_substitute(
            {
                "track_auto": track_auto,
                "title_auto": title_auto,
                "discnumber": discnumber,
                "tracknumber": tracknumber,
                "title": title,
                "artist": artist,
            }
        )
        filename = filename.replace("/", self.ctx.config.path_replace_slash)
        filename = sanitize_filename(
            filename + Path(track.filename).suffix, replacement_text=self.ctx.config.path_replace_invalid, platform=self.ctx.config.path_compatibility
        )
        return filename

    def _fix_use_generated(self, album: Album):
        album_path = self.ctx.config.library / album.path

        tracks_to_rename = [track for track in sorted(album.tracks) if self._generate_filename(album, track) != track.filename]
        new_filenames = [self._generate_filename(album, track) for track in tracks_to_rename]

        old_filenames_lower = {str.lower(track.filename) for track in tracks_to_rename}
        new_filenames_lower = {str.lower(filename) for filename in new_filenames}
        if new_filenames_lower.intersection(old_filenames_lower):
            # additional rename if tracks are swapping filenames
            self.ctx.console.print("A new filename is the same as an old filename (ignoring case) - extra rename required")
            for track in tracks_to_rename:
                num = 0
                while (temp := (album_path / track.filename).with_suffix(f".{num}")) and temp.exists():
                    num += 1
                original_filename = track.filename
                track.filename = temp.name
                self.ctx.console.print(f"Temporarily renaming {escape(original_filename)} to {escape(track.filename)}", highlight=False)
                rename(album_path / original_filename, album_path / track.filename)

        for ix, track in enumerate(tracks_to_rename):
            new_filename = new_filenames[ix]
            self.ctx.console.print(f"Renaming {escape(track.filename)} to {escape(new_filename)}", highlight=False)
            rename(album_path / track.filename, album_path / new_filename)
            track.filename = new_filename

        return FixResult.CHANGED_ALBUM

    def _pad(self, field_name: Literal["tracknumber", "tracktotal", "discnumber", "disctotal"], value: str, total: int) -> str:
        if not value or not int(value):
            return ""
        if not self.ctx.config.checks[CheckZeroPadNumbers.name]["enabled"]:
            return value
        policy = ZeroPadPolicy.from_str(str(self.ctx.config.checks[CheckZeroPadNumbers.name][f"{field_name}_pad"]))
        return apply_pad_policy(value, policy, total)
