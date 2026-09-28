# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note on earlier history:** releases before 2.1.0 were never tagged and the
> version was recorded only as a constant in `src/client.py`. The entries below
> were reconstructed from the git history, so they describe what changed rather
> than what was formally released.

## [Unreleased]

### Added

- `duplicate_work_package` – copies a work package into a new one. OpenProject
  API v3 has no native copy endpoint, so the source is read and recreated from
  its fields: subject, description, `scheduleManually`, `ignoreNonWorkingDays`
  and the type, status, priority, assignee, responsible, version, category and
  parent links. Custom fields are carried over through both channels – plain
  values in the body and link-typed ones (CustomOption, User, Version) via
  `_links.customFieldN`.
  - The copy starts with **time tracking and progress at zero**: dates,
    estimates, duration and `percentageDone` are not carried over.
  - Read-only and derived fields (`id`, `lockVersion`, `createdAt`, `spentTime`,
    `derived*`, `author`) are skipped; the copy is authored by the API key owner.
  - Attachments, comments, relations, watchers and children are **not** copied.
    When the description embeds images, the copy still points at the original's
    attachments – the tool response says so explicitly.
  - The underlying request is sent with `?notify=false` so duplicating does not
    email the watchers.
- `custom_fields` parameter on `create_time_entry`, `update_time_entry`,
  `create_work_package` and `update_work_package`. Values are passed through
  unchanged as `customField<N>`; the response echoes the stored value of every
  requested field so the caller can verify it was saved. `update_time_entry` now
  accepts a call that changes only custom fields.
- Images embedded in **comments** are now detected alongside those in the
  description. `get_work_package_context` reports them separately and
  deduplicates IDs already listed for the description.

### Changed

- Default `max_dimension` for images lowered from 1600 px to **1092 px**. Below
  that threshold the model does not rescale the image on its own, so this cuts
  roughly a third of the tokens per screenshot with no practical loss of
  legibility. Callers can still pass any value in the 64–4096 range.

### Disabled

- `upload_attachment` is commented out rather than removed – attachments are
  uploaded manually through the OpenProject UI for now. The client method
  (`OpenProjectClient.upload_attachment`) and its tests are untouched, so the
  tool can be restored by uncommenting it in `src/tools/attachments.py`, its
  entry in `WRITE_TOOLS` and the related tests.

## [2.0.0] – 2025-12-02

Architectural rewrite from a single-file server onto the FastMCP framework.
No tool was dropped: the original monolith was kept in the repository as
`openproject-mcp.legacy.py`.

### Added

- `src/` package layout: `client.py` (async OpenProject API v3 client),
  `server.py` (FastMCP initialization), `tools/` and `utils/`.
- HTTP and SSE transports (`openproject-mcp-http.py`, `openproject-mcp-sse.py`)
  and FastMCP Cloud deployment support, so the server no longer has to run
  locally for every user.
- Agent context tooling: `get_work_package_context` (details, custom fields,
  comments, attachments, relations and hierarchy in one parallel call, with a
  failing section reported inline instead of breaking the response),
  `get_allowed_statuses`, `list_work_package_activities`, watcher tools,
  attachment tools (`list_work_package_attachments`, `get_attachment`,
  `upload_attachment`), work discovery tools (saved queries, notifications,
  `list_my_work_packages`), version tools and code-link integrations.
- `format="markdown"` (default) or `format="json"` on read tools.
- Read-only mode via `OPENPROJECT_READ_ONLY`, backed by a registry of write
  tools (`src/utils/safety.py`) that a test keeps in sync.
- Image preparation for MCP responses (`src/utils/images.py`): proportional
  downscaling and recompression through Pillow, with a graceful fallback when
  Pillow is missing.
- TTL cache for schemas, types, statuses and priorities.
- Test suite with fixtures, covering the client, the tools and read-only mode.

### Known issues

- The version is recorded in two places that disagree: `pyproject.toml` says
  `1.0.0` while `src/client.py` says `2.0.0`. The constant is only used for the
  `User-Agent` header.
- `list_time_entry_activities` falls back to hard-coded activity IDs 1–4, which
  need not exist on a given instance.

## [1.0.0]

Initial single-file MCP server (`openproject-mcp.legacy.py`) covering project,
work package, membership, relation, hierarchy, time entry, version, news and
weekly report tools.

[Unreleased]: https://github.com/BlazejKalkowski/openproject-mcp-server/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/BlazejKalkowski/openproject-mcp-server/releases/tag/v2.0.0
