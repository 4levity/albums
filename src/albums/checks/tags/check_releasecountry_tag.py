import logging
from typing import Final, override

from ...checks.tag_policy import Policy
from ...tagger.folder import AlbumTagger, Cap
from ...types import Album, BasicTag
from ..base_check_tag_per_album import BaseCheckTagPerAlbum

logger: Final = logging.getLogger(__name__)


class CheckReleaseCountryTag(BaseCheckTagPerAlbum):
    name = "release-country-tag"
    tag = BasicTag.RELEASECOUNTRY

    @override
    def check(self, album: Album):
        if self.presence != Policy.NEVER and not all(AlbumTagger.supports(track.filename, Cap.VORBIS_COMMENT) for track in album.tracks):
            # this tag is only supported for vorbis comments, so if any track is not vorbis comment, the only reasonable policy is NEVER
            # (only makes a difference if the album is a mix of vorbis and non-vorbis tracks)
            return super().do_check(album, Policy.NEVER)
        # else
        return super().check(album)
