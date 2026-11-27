---
status: awaiting-user
mode: interactive
canonical_location: docs/plans/tidal-playlist-mcp.md
last_updated: 2026-11-27
current_phase: Phase 1 - Connected playlist discovery
current_step: Phase 1 user test
next_action: Collect user-provided live read-only checkpoint observations.
blockers: none
---

# TIDAL Playlist MCP Server

## Plan Metadata

- Delegation: single agent; a new repository and sequential product decisions do not yet justify parallel implementation.
- Storage: `docs/plans/tidal-playlist-mcp.md`.
- Goal: Build a simple local TIDAL playlist CRUD MCP server using `tidalapi`, with instructions enabling an agent to help an archivist organize a large collection interactively.
- Success criteria: A stdio MCP client can enumerate a large playlist/folder collection and its items without silently truncating results, and perform supported playlist, item, and folder CRUD; instructions guide an agent to ask about playlist intent and reason about organization without building a dedicated cleanup engine; mutation safety and errors are explicit; automated tests require no live credentials.
- Constraints: Interactive checkpoints; keep existing license unless the owner explicitly decides otherwise; protect account credentials and existing playlists; do not make real account changes during planning.
- Exclusions: the user's separate future webapp, hosted service, automatic one-shot cleanup engine, playlist-comparison tools, persistent subset relationships, synchronization, embedded AI or similarity classifier, playback, and unrelated catalog features. Basic retrieval and CRUD are preferred; add specialized tools only when an agent genuinely needs them.
- Client: VS Code Copilot, using local stdio.
- Admission review, 2026-11-11T16:53:01+01:00: `not-ready`; interactive; normalized SHA-256 `99dcfbefe235a7177cde3f361fe3eec3c83a3df7c38c4cda2cb930f38fc296c5` supplied by executor and not independently verified by the reviewer. Blocking finding: the checkpoint does not explicitly require an authorized nested-folder pagination check; if a suitable collection is unavailable, consult the user rather than claiming completeness. Warning: pin and retest the dependency because the request helper is non-public. A fresh ready review and matching fingerprint are required before implementation.
- Admission review, 2026-11-11T17:51:46+01:00: `ready`; interactive; repair cycle 1 of 2; no errors. Normalized SHA-256 `7119ebc6f0eb8fab22674d8ab92fe1c7c3f3501c79f715f37bd19178cac13e74` supplied by executor, unverified by reviewer, and recomputed and matched by executor after review. Warning: pin and retest the dependency because the request helper is non-public. Live pagination remains unverified.

## Execution Protocol

Any agent executing this plan follows these rules.

1. Resume the active incomplete step: unresolved `[?]` or `[!]` takes precedence, then `[-]`, then the first dependency-ready `[ ]` in the current phase. Keep frontmatter synchronized. If multiple active steps conflict without a declared parallel group, ask one focused clarification. Never cross an interactive phase boundary without confirmation.
2. Status markers: `[ ]` pending, `[-]` in progress, `[x]` complete, `[!]` blocked, `[?]` awaiting user.
3. Elaborate a phase's steps only when the user asks to start it; confirm the steps with the user before executing.
4. Phase boundaries are revisable: split, merge, reorder, or rename phases when evidence changes the design, and record the decision and rationale.
5. Mark a step `[x]` only when its Check has valid recorded execution evidence. Label checks step, phase, or final; use focused step checks and inspect package-script expansion. Reuse passing evidence unless relevant code, dependencies, configuration, or environment changed, applicability is uncertain, or observations contradict it. Prompt for any actions ready for manual testing, or state "No checkpoint tests yet."
6. Persist state before implementation, when blocked, at handoff, and after each verified step. Combine step result, evidence, and next-state update in one edit; persist scope changes before acting on them. Frontmatter owns mutable state; steps own evidence. Do not persist routine intermediate tool results separately.
7. If a step's premise is false or it needs changes outside its scope, mark it `[!]`, log the evidence, and ask the user. Do not improvise around it.
8. Phase gate: cover the phase's full Validation with valid evidence, reusing passing checks and running uncovered checks. Stop, collect any required user-test evidence, then ask whether to continue, revise, or pause.
9. Git inspection requires an explicitly requested Git operation or a concrete approved-plan prerequisite. Suggest commit messages only when requested. Never infer authorization or completion from staged state. Git is read-only; never stage, commit, branch, or push.
10. When a phase completes, collapse each step to a one-line result that retains its Check and outcome as the sole evidence record. Keep Validation prescriptive; remove commands and outcomes from completed-phase Progress Log entries; verify each evidence pair appears only on its owning step.
11. When every phase passes, establish passing final validation evidence, reusing identical valid phase checks and running remaining checks, set status to completed, then move this file to `docs/plans/archive/` and never touch the old path.

## Decisions

- 2026-11-11: Plan is repo-backed and interactive, as requested.
- 2026-11-11: Use VS Code Copilot as the first MCP client for Phase 1.
- 2026-11-11: Store TIDAL session credentials in a permission-restricted local file, not Keychain, with a matching ignore rule; do not store the account password.
- 2026-11-11: Phase 1 uses the official Python MCP SDK, `tidalapi`, Python packaging with `pip` and `pytest`; select and record released dependency versions after checking compatibility. The server uses stdio, and an explicit terminal login command performs device authorization outside the protocol stream.
- 2026-11-11: The user approved an isolated cursor adapter using the released library's underlying request helper for collection listings. This helper is not a public API; validate its behavior with simulated responses and a user-authorized read-only live check, and surface incomplete results or errors rather than claiming completeness.
- 2026-11-11: Use a local stdio MCP server. Expose small, composable CRUD operations for playlists, playlist items, and folders; use agent instructions for cleanup requiring judgment about names, items, and similar playlist purposes. Do not build a dedicated one-time cleanup workflow without separate justification.
- 2026-11-11: Reserve MCP-based agent work for tasks needing intelligence. The user intends a separate webapp to use the API directly and remember or manage playlist relationships without agents; designing or building it is outside this plan. Do not add a comparison tool, subset storage, or synchronization here unless a future concrete agent need justifies it.
- 2026-11-11: Agent instructions should ask the owner why playlists exist and what belongs in them, distinguish confirmed intent from inferred overlap, and obtain consent before making the agreed changes. These instructions are guidance, not an authorization boundary; server-side validation and client permissions remain necessary.
- 2026-11-11: The repository contains an AGPL version 3 license text. `tidalapi` identifies itself as LGPL-3.0-or-later; its source and redistribution obligations need to be accounted for when packaging or distributing this server. License compatibility and notices are not a substitute for legal advice.
- 2026-11-11: `tidalapi` is unofficial, currently specifies Python 3.11 or newer, and provides session login and playlist item APIs. Verify the selected released version and its actual behavior before implementation; do not rely on an unpinned upstream branch.

## Deferred Items

- Exact user-confirmation granularity, audit/recovery approach, and treatment of playlist-intent notes: agree with the user before elaborating the relevant phase; do not assume inferred intent may overwrite playlist descriptions.

## Phase 1: Connected playlist discovery

### Tangible output

A locally runnable stdio MCP server that authenticates a TIDAL account and exposes paginated, read-only playlist, folder, and item inventory to a client.

### Completion criteria

The user can connect and inspect playlist metadata, folder hierarchy, and playlist items with identifiers and sufficient metadata for an agent to reason about names and contents. Pagination exposes continuation or proves exhaustion without silently truncating nested folders or long playlists; entries preserve order, duplicate occurrences, and media type. Automated tests cover authentication boundaries, pagination, errors, and credential non-disclosure.

### Context

The repository currently has only a minimal `README.md`, a Python `.gitignore`, and `LICENSE`; there is no application or test suite. Upstream's [simple example](https://github.com/EbbLabs/python-tidal/blob/main/examples/simple.py) uses a session file. Its [session implementation](https://github.com/EbbLabs/python-tidal/blob/main/tidalapi/session.py) defaults to printing login instructions, and PKCE also reads standard input; neither can be allowed to corrupt an MCP stdio stream. Its [user APIs](https://github.com/EbbLabs/python-tidal/blob/main/tidalapi/user.py) expose folder listing with cursors, while [folder item listing](https://github.com/EbbLabs/python-tidal/blob/main/tidalapi/playlist.py) accepts offsets; upstream notes some collection endpoints ignore offsets. These observations describe upstream `main`, not necessarily a released package; verify the selected release and actual pagination semantics for nested folders rather than assuming these APIs enumerate everything. Playlist items can include tracks and videos. Authentication must not leak tokens.

### Dependencies and risks

No preceding implementation phase is required; Python, the MCP SDK, `tidalapi`, and pytest are package dependencies. The library is unofficial, upstream API behavior may change, pagination differs among endpoints, and real authentication requires the user's account. Establish secure token storage and failure reporting before use. If complete folder enumeration is not supported safely by the selected library, surface the limitation and consult the user rather than claiming completeness.

### Steps

- [x] P1.S1: Establish a Python project and read-only stdio MCP skeleton; inspect the selected released `tidalapi` package for authentication, request helper, and playlist-item pagination support. Record versions and API evidence on this step. The approved cursor adapter fills the collection-listing gap; block if the needed request interface is unavailable or its documented cursor behavior cannot be established.
  - Files: `pyproject.toml`, `src/tidal_playlist_mcp/`, `tests/test_server.py`.
  - Check (step): After declaring dependencies, run `python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]' && .venv/bin/python -m pytest -q tests/test_server.py`. Tests must exercise MCP initialization and tool discovery through the SDK with a fake backend, and prove that stdio contains only protocol messages. Record selected package versions and cited source evidence for authentication, cursor request/response semantics, playlist-item pagination, and endpoint limits on this step; document that nested-folder behavior requires live validation. Block and ask the user if the request helper or documented cursor behavior cannot be established.
  - Depends: none.
  - Evidence (2026-11-11): `python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]' && .venv/bin/python -m pytest -q tests/test_server.py` passed (2 tests); after strengthening stdout checking, `.venv/bin/python -m pytest -q tests/test_server.py` passed (2 tests). Selected Python 3.15.2, MCP SDK 2.3.0, `tidalapi` 0.8.11, and pytest 9.2.0. Its [folder APIs](https://github.com/EbbLabs/python-tidal/blob/v0.8.11/tidalapi/user.py) expose `offset` but no cursor, and its [folder item API](https://github.com/EbbLabs/python-tidal/blob/v0.8.11/tidalapi/playlist.py) likewise uses offset. [Upstream main](https://github.com/EbbLabs/python-tidal/blob/main/tidalapi/user.py) states the collection endpoint ignores offsets and instead uses cursors. Complete nested-folder enumeration remains subject to live testing.
  - Investigation (2026-11-11): The [upstream cursor fix](https://github.com/EbbLabs/python-tidal/commit/1d2c280964b9c3b79cc1a5397d1d4cee70287663) documents forwarding a response cursor to the same collection endpoint; upstream's added test covers root playlists, not nested playlist listings. The [released request helper](https://github.com/EbbLabs/python-tidal/blob/v0.8.11/tidalapi/request.py) can issue authenticated GET requests and access the response cursor but explicitly says it is not intended for external use. A small isolated adapter is plausible, but live nested-folder behavior and completeness remain unverified. Separate playlist-item pagination uses a different endpoint and must also be verified. No account access or implementation was performed.
  - Investigation (2026-11-11): A [TIDAL user's report](https://github.com/iamprivacy/Waves/issues/11) explicitly describes folders inside folders; released `tidalapi` also exposes a `parent_id` when creating folders. This is evidence of support, not an official TIDAL guarantee or a live test. A non-root folder containing playlists is sufficient to exercise listing within a folder; it does not itself need to be a subfolder.
  - Investigation (2026-11-11): The [released session implementation](https://github.com/EbbLabs/python-tidal/blob/v0.8.11/tidalapi/session.py) provides device login but its refresh method does not retain a newly returned refresh token; [upstream main](https://github.com/EbbLabs/python-tidal/blob/main/tidalapi/session.py) identifies token rotation as necessary. P1.S2 must handle this and test it rather than assuming release behavior is sufficient. Playlist items support offsets and a 100-item limit according to the released playlist API; live behavior remains unverified.
- [x] P1.S2: Implement a separate terminal device-login command and session loading for the server. Store access/refresh tokens and expiry data outside the repository at `~/.config/tidal-playlist-mcp/session.json` so the server can reuse and refresh its login. On macOS, require the dedicated directory and file to be owned by the current user, not symlinks, with directory mode `0700` and regular file mode `0600`; refuse unsafe existing paths and permission failures. Write rotated tokens using a private temporary file and atomic replacement so interruption does not leave a partial credential file; surface persistence errors. On platforms without equivalent verified protections, fail explicitly instead of silently weakening them. Do not log secrets, and report missing/invalid sessions without prompting on MCP stdin. Add a defensive `.gitignore` entry for accidental in-repo session files.
  - Files: `src/tidal_playlist_mcp/`, `tests/test_auth.py`, `.gitignore`.
  - Check (step): `.venv/bin/python -m pytest -q tests/test_auth.py`. Tests use temporary directories and fake OAuth sessions; verify ownership and modes, refusal of symlinks, non-regular files, unsafe ownership or modes, and permission-setting failures; simulate interrupted replacement and verify no partial credential file; verify refresh-token persistence, missing/invalid sessions, terminal-only login, and failure with an explicit error when no terminal is available. Capture all streams to verify login instructions go to the terminal, neither mode outputs credentials, and server mode neither prompts on MCP stdin nor writes non-protocol output to stdout.
  - Depends: P1.S1.
  - Blocker (2026-11-11): `.venv/bin/python -m pytest -q tests/test_auth.py` failed: 1 failed, 10 passed. `test_refuses_unsafe_modes_and_ownership[file]` replaces `os.fstat` with an incomplete result, causing `AttributeError: 'types.SimpleNamespace' object has no attribute 'st_size'`. Earlier 9-test success was superseded by this run; authentication is not yet verified.
  - Evidence (2026-11-26): Replaced the incomplete mock with a modified `os.stat_result`. `.venv/bin/python -m pytest -q tests/test_auth.py` passed (11 tests). Live authentication remains untested.
- [x] P1.S3: Add simple read-only MCP tools to list the immediate folders and playlists under a specified parent, inspect playlist metadata, and list playlist items. Use an isolated cursor adapter around the released library's request helper for collection listings, with no change to the library itself. Use stable IDs and explicit page/continuation information, include ownership and useful metadata, and preserve order, duplicate occurrences, and track/video types. Check nested-folder and item pagination separately; expose upstream errors, limits, and incomplete results rather than claiming success.
  - Files: `src/tidal_playlist_mcp/`, `tests/test_inventory.py`.
  - Check (step): `.venv/bin/python -m pytest -q tests/test_inventory.py`. Fake responses cover multiple pages beyond upstream limits, nested folders, repeated names and track IDs, mixed media, empty pages, malformed or repeated/non-advancing continuations, ignored offsets, capped responses, and API errors; assert exact results, bounded termination, and explicit incomplete/limited outcomes instead of false exhaustion.
  - Depends: P1.S1, P1.S2.
  - Evidence (2026-11-26): `.venv/bin/python -m pytest -q tests/test_inventory.py` passed (13 tests). Nested-folder, collection cursor and item-offset behavior remain subject to the live checkpoint.
- [x] P1.S4: Document local installation, terminal login, session-file location and protection, VS Code stdio configuration, read-only tools, and cleanup of local credentials. Add an end-to-end mocked MCP client test that initializes the server and calls each read tool across page boundaries.
  - Files: `README.md`, `tests/test_server.py`.
  - Check (step): `.venv/bin/python -m pytest -q tests/test_server.py`; inspect the README against the actual executable and tool schemas, including the correct VS Code launch configuration and re-login instructions.
  - Depends: P1.S2, P1.S3.
  - Blocker (2026-11-26): `.venv/bin/python -m pytest -q tests/test_server.py` failed (2 passed, 1 failed): `test_client_calls_inventory_tools_across_pages` received `structured_content=None` for `list_collection`, so indexing it raised `TypeError`. Investigate the actual MCP response before choosing a correction; phase validation and live testing have not run.
  - Investigation (2026-11-27): A mocked SDK client call returned JSON in a text content block, with `structured_content=None` and no output schema. The client test needs to decode the text response.
  - Evidence (2026-11-27): `.venv/bin/python -m pytest -q tests/test_server.py` passed (3 tests); inspected the README against the executable, project entry point, login command, and SDK tool input schemas.

### Validation

Phase check: `.venv/bin/python -m pytest -q tests/test_auth.py tests/test_inventory.py tests/test_server.py`, including the mocked MCP protocol smoke test. Inspect the selected release and README for consistency with the documented client invocation. Then collect the authorized read-only live-account User Test below; do not access or modify the user's actual account without authorization.

### Checkpoint

Phase validation evidence (2026-11-27): `.venv/bin/python -m pytest -q tests/test_auth.py tests/test_inventory.py tests/test_server.py` passed (27 tests). The selected release, README, executable, and tool schemas were inspected. Live account behavior remains unverified.

[?] Awaiting user-provided read-only test evidence.

User Test: Run the documented login command, configure the server in VS Code Copilot, and ask it to list folders and inspect one chosen playlist. Exercise read-only pagination in the user's folder with more than 50 playlists, including every page. If a folder inside another folder is available and the user authorizes it, inspect that subfolder too, including additional pages if it has enough items; otherwise consult the user before phase completion and do not claim its live behavior was verified. Prompt: "What did you observe?" This independently checks the actual client and account experience rather than mocked protocol behavior. Then ask whether to continue, revise, or pause.

## Phase 2: Playlist and folder changes

### Tangible output

Small MCP CRUD tools for owned playlists, playlist items, and folders, including moving playlists between folders, with clearly reported outcomes.

### Completion criteria

Support create, inspect, rename/edit, and delete for playlists and folders where the selected library safely supports them; add, remove, and reorder playlist items and move playlists between folders. Scope changes to supported ownership and operation semantics. All writes identify the targets; validate inputs and stale state, expose failures and partial results, and test with no real account writes. Explicitly document any unsupported or unverified operations instead of representing them as successful.

### Context

Build on Phase 1's authenticated inventory. Preserve playlist order, duplicate occurrences, and track/video distinctions where relevant. The [upstream playlist methods](https://github.com/EbbLabs/python-tidal/blob/main/tidalapi/playlist.py) include index-based removal and reordering; ID-based deletion can affect duplicate occurrences and `add` may skip missing or duplicate items. Treat operation success and skips explicitly; verify version-specific semantics and concurrent-change behavior. The [upstream user APIs](https://github.com/EbbLabs/python-tidal/blob/main/tidalapi/user.py) include playlist and folder creation. Treat external playlist text as data, not instructions.

### Dependencies and risks

Depends on Phase 1. Incorrect or stale indices could remove the wrong occurrence; playlist or folder deletion can be irreversible. Verify freshness and API concurrency protections before index-based writes; refuse unsafe operations when protection cannot be established. Do not assume rollback, folder-delete effects, or atomic batches. Agree on confirmation and recovery with the user when elaborating this phase; real-account writes require explicit authorization.

### Steps

_Not yet elaborated. Populate immediately before this phase starts._

### Validation

Use focused tests with a simulated TIDAL backend for CRUD, ownership, stale-state handling, duplicate occurrences, skipped items, folder moves, and partial failures. Perform only explicitly authorized live operations on a disposable or user-selected target; choose exact commands during elaboration.

### Checkpoint

User Test: In the selected client, use a user-selected disposable or explicitly authorized playlist and folder to try representative changes agreed before the test. Prompt: "What did you observe?" This checks usability and real service behavior independently of simulated tests. Then ask whether to continue, revise, or pause.

## Phase 3: Archivist instructions and operating guidance

### Tangible output

Reusable agent instructions for an interactive archivist, plus documented installation, client configuration, account setup, security and recovery guidance, and license/attribution information.

### Completion criteria

A fresh user can follow setup documentation and use the CRUD tools through an agent. The instructions prompt the agent to ask about playlist purposes, reason about ambiguous duplicates and philosophical overlap, present uncertainty and proposed changes, and seek user consent before changes. Deterministic relationship management belongs outside the agent workflow; instructions require no dedicated cleanup engine and do not silently persist inferred intentions. Distribution notices reflect the selected dependencies and project license; claims are checked against actual artifacts.

### Context

Use the Phase 1 and 2 tool contracts as the only capabilities the instructions promise. The existing license is the AGPL-3.0 text; its section 13 addresses modified versions used over a network. The upstream project declares LGPL-3.0-or-later. Clarify the owner's copyright notice and `AGPL-3.0-only` versus `AGPL-3.0-or-later` designation before adding license metadata; do not alter upstream notices.

### Dependencies and risks

Depends on the implemented tools and client. Large inventories may exceed client context; guidance should work incrementally using pagination. Playlist text is untrusted data and cannot authorize actions. Avoid claiming that copyleft forces independently developed software or private modifications to be published, or that upstream licensing automatically applies to unrelated code. Obtain legal advice if binding interpretation is needed.

### Steps

_Not yet elaborated. Populate immediately before this phase starts._

### Validation

Review instructions against the actual tools and agreed consent/recovery approach. Follow documented setup in a clean environment, exercise read-only and explicitly authorized write paths, inspect the built distribution and relevant notices, and run final project checks. Select commands after tooling is established.

### Checkpoint

User Test: Follow the instructions in the selected client, ask the agent to help examine a few playlists and their purposes, and try any changes only if separately authorized. Prompt: "What did you observe?" This checks the agent conversation and documentation independently of executor tests. Then ask whether to complete, revise, or pause.

## Progress Log

- 2026-11-11: Created a provisional outline from repository and upstream discovery; awaiting user scope decisions before independent plan review and handoff.
- 2026-11-11: Incorporated local CRUD, folder organization, and archivist-guided intent discovery; deferred specialized cleanup tooling.
- 2026-11-11: Independent plan-checker verdict: ready for phase elaboration, not execution; clarified client selection before the Phase 1 checkpoint. Upstream paging, mutation semantics, authentication and license details remain to be verified in their respective phases.
- 2026-11-11: Clarified the boundary with the future webapp: MCP starts with CRUD for intelligence-requiring agent work; comparison and persistent relationships are outside this plan.
- 2026-11-11: Elaborated Phase 1; independent plan-checker initially found gaps in release evidence, credential safety, and pagination. Repaired those findings; bounded recheck verdict ready for user confirmation. Added the recheck's non-blocking terminal-I/O clarification.
- 2026-11-11: User approved the elaborated Phase 1; hand off for execution starting with P1.S1.
- 2026-11-11: User approved the isolated collection cursor adapter after the released library's offset limitation was discovered.
- 2026-11-11: User authorized a read-only checkpoint using their folder with more than 50 playlists; subfolder behavior is a separate, conditional check.
