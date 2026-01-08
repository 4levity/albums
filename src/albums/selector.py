import enum
import re


class MatchType(enum.Enum):
    EXACT = enum.auto()
    PARTIAL = enum.auto()
    RE = enum.auto()


def select_albums(albums: dict, match_paths: list[str], collections: list[str], match_type: MatchType):
    def album_filter(album: dict):
        def match_param(target, candidate):
            if match_type == MatchType.RE:
                return re.search(target, candidate) is not None
            elif match_type == MatchType.PARTIAL:
                return target in candidate
            elif match_type == MatchType.EXACT:
                return target == candidate
            raise ValueError("unknown MatchType")

        if len(match_paths) > 0:
            match = False
            for album_match in match_paths:
                if match_param(album_match, album["path"]):
                    match = True
            if not match:
                return False
        if len(collections) > 0:
            match = False
            for target_collection in collections:
                if target_collection in album.get("collections", []):
                    match = True
            if not match:
                return False
        return True

    return sorted(filter(album_filter, albums.values()), key=lambda a: a["path"])
