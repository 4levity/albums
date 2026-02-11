import logging

from ..types import Album
from .base_check import Check, CheckResult, ProblemCategory

logger = logging.getLogger(__name__)

OPTION_DELETE_ALL_COVER_IMAGES = ">> Delete all cover image files: "
OPTION_SELECT_COVER_IMAGE = ">> Mark as front cover source: "


class CheckInvalidImage(Check):
    name = "invalid_image"
    default_config = {"enabled": True}

    def check(self, album: Album) -> CheckResult | None:
        album_art = [(track.filename, True, track.pictures) for track in album.tracks]
        album_art.extend([(filename, False, [picture]) for filename, picture in album.picture_files.items()])
        files: list[str] = []
        issues: set[str] = set()
        for filename, embedded, pictures in album_art:
            for picture in pictures:
                if picture.load_issue and "error" in picture.load_issue:
                    files.append(f"{filename}{f'#{picture.embed_ix}' if embedded else ''}")
                    issues.add(str(picture.load_issue["error"]))
        if issues:
            return CheckResult(ProblemCategory.PICTURES, f"invalid images ({', '.join(issues)}): {', '.join(files)}")
