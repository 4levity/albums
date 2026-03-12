from collections import defaultdict
from functools import reduce
from typing import Any

from rich.markup import escape

from ...database.models import AlbumEntity
from ...tagger.types import Picture, PictureType
from ...types import CheckResult
from ..base_check import Check


class CheckConflictingEmbedded(Check):
    name = "conflicting-embedded"
    default_config = {"enabled": True, "cover_only": False}
    must_pass_checks = {"duplicate-image"}

    def init(self, check_config: dict[str, Any]):
        self.cover_only = bool(check_config.get("cover_only", CheckConflictingEmbedded.default_config["cover_only"]))

    def check(self, album: AlbumEntity) -> CheckResult | None:
        for track in album.tracks:
            pics_by_type: defaultdict[PictureType, list[Picture]] = defaultdict(list[Picture])
            pics_by_type = reduce(lambda acc, item: acc[item.picture_type].append(item.to_picture()) or acc, track.pictures, pics_by_type)
            conflict_type = next(
                (t for t in pics_by_type if len(pics_by_type[t]) > 1 and (t == PictureType.COVER_FRONT or not self.cover_only)), None
            )
            if conflict_type:
                # TODO preview and remove or change type of conflicting images
                message = f"there are {len(pics_by_type[conflict_type])} different images for {conflict_type.name} in {escape(track.filename)}"
                return CheckResult(message)
