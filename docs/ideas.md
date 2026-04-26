---
icon: lucide/flask-conical
---

# Ideas

## General features

- When running import check/fix, don't change source files (configurable? 1. fix
  in-place, 2. use temp dir 3. copy to library, then fix)
- Select/filter albums based on stream info, recent access, etc
- Support additional file formats
- Dynamic collections e.g. by tag value or partial path
- Option to use ID3 2.3 instead of 2.4 (if people still do that?)
- Improve Unicode support (e.g. case insensitive comparisons)
- Localize interface (per volunteer)

### More checks and fixes

- more genre features
    - limit genres to user-defined list
    - guess genre w/ albums from same artist (in library, not from import scan)
    - save mappings from any-genre to user-genres
    - use $genre in path templates
- read album comment tags (various) and add per-album check(s)
- scan date(s), require/special validate, use in file/folder name templates
- many suggested fixes for current no-fix check failures in TODOs
- low bitrate or suboptimal codec
- not all tracks encoded the same (file type or bitrate target)
- parent folder doesn't match artist if using artist/album
- automatic visual similarity check for front cover art, so it can be stored in
  multiple formats and resolutions without disabling uniqueness check
