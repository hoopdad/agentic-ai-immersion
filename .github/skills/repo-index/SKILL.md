---
name: repo-index
description: Use at the start of work in a repository and after file adds, deletes, or architecture-significant changes. Maintains and uses a compact repository index so agents navigate by architecture instead of grep.
---

# Repo index

Use `<root>/.github/repo-index.md`.

1. Read it first. Refresh if absent or stale from structural changes, relevant commits, or current work.
2. Build from the file tree, manifests, entry points, architecture docs, and representative files; do not grep.
3. Keep it compact:
   - functional areas: purpose and owning paths
   - technical layers: entry points, dependency flow, boundaries
   - navigation: common task -> files
   - important conventions and tests
   - freshness: commit plus added/deleted paths considered
4. Navigate from the index. Search text only when the index cannot locate the target; then improve the index.
5. Refresh after adding or deleting files or changing architecture, boundaries, entry points, ownership, or major dependencies.

Preserve useful existing notes and avoid exhaustive file lists.
