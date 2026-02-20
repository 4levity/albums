---
icon: lucide/flask-conical
---

# Ideas

## General features

- Scan, check and fix albums outside of library
    - Operate on folders without using a database
    - Import newly scanned and fixed albums to library
- Select/filter albums based on track tags, recent access, other
- Support additional file formats
    - Comprehend standard tags (artist, album, title. track)
    - Better support for MP4 (M4A, M4B, M4P) and other files
    - Add other extensions to default scan

### More checks and fixes

- low bitrate or suboptimal codec
- not all tracks encoded the same (file type or kbps target)
- track filename doesn't match title, doesn't include track/disc number
- album folder doesn't match album name
- parent folder doesn't match artist if using artist/album
- automatic visual similarity check for front cover art, so it can be stored in
  multiple formats and resolutions without disabling uniqueness check
