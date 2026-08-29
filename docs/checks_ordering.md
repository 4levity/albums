---
icon: lucide/list-ordered
---

# Ordering And Dependencies

## Order

Enabled checks will run in order on each album:

1. `duplicate-pathname` check _("Path and File")_
1. `illegal-pathname` check _("Path and File")_
1. `file-extension` check _("Path and File")_
1. `unreadable-track` check _("Path and File")_
1. `extra-whitespace` and `legacy-fields` checks _("General Fields")_
1. All "Numbering" checks
1. Remaining "General Fields" and "Album Fields" checks
1. All "Pictures" checks
1. Remaining "Path and File" checks

Within each category, the checks run in the order they are listed on the
check pages.

## Dependencies

Individual checks are mostly independent, but some checks will not run on an
album unless a previous check ran and passed. For example, the specific fix from
the `disc-in-tracknumber` check should be applied before
`invalid-track-or-disc-number` flags the track number as invalid. And, when the
`invalid-image` check doesn't pass, none of the other "Pictures" checks can run.
Other dependencies are listed on each check's page.
