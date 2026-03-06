# Memory Index System Design

Date: 2026-02-18
Status: Approved

## Problem

Agent has no "directory awareness" of its own memories. On first turn, it reads hardcoded files (user_profile.md, instructions.md), and discovers project files only when the user explicitly mentions a project name. As memories grow, this approach wastes tokens and misses relevant context.

## Solution: index.md

A single index file (`/memories/index.md`) that Agent reads on first turn to understand what memories exist. Replaces the current "read everything" approach with "read index, then fetch on demand."

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Who maintains index? | Agent (real-time) + backend (PDF upload) | Agent knows semantic summaries; backend guarantees PDF entries |
| Index content per entry | Path + detailed summary + update time | Summaries must contain key data/numbers to avoid missing important info |
| First-turn loading | index.md + user_profile.md + instructions.md | Index for awareness, profile for preferences, instructions for behavior rules |
| PDF indexing | Backend auto-writes on upload | Reliable, no Agent involvement needed |

## index.md Format

```markdown
# Memory Index

## User Profile
| File | Summary | Updated |
|------|---------|---------|
| /user_profile.md | [80-150 chars: investment preferences, risk appetite, key interests] | 2026-02-15 |
| /instructions.md | [80-150 chars: behavior rules, correction history] | 2026-02-10 |

## Projects
| File | Summary | Updated |
|------|---------|---------|
| /projects/CopperMineA.md | [80-150 chars: key data, IRR, recommendation, risks, numbers] | 2026-02-15 |

## Decisions
| File | Summary | Updated |
|------|---------|---------|
| /decisions/2026-02-01_CopperMineA_hold.md | [80-150 chars: decision rationale, timeline] | 2026-02-01 |

## Documents
| File | Summary | Updated |
|------|---------|---------|
| /documents/PRD_v1.0.md | [20-50 chars: filename, pages, parse method] | 2026-02-18 |
```

Summary length rules:
- Projects & Decisions: 80-150 chars, must include key data and numbers
- Documents: 20-50 chars, filename + page count sufficient
- User Profile & Instructions: 80-150 chars

Category rules (by path):
- `/user_profile.md`, `/instructions.md` -> User Profile section
- `/projects/*.md` -> Projects section
- `/decisions/*.md` -> Decisions section
- `/documents/*.md` -> Documents section

## Changes Required

### 1. prompts.py (Agent system prompt)

**First-turn reading** (replace lines 85-91):
- Read `/memories/index.md` (memory index)
- Read `/memories/user_profile.md` (user preferences)
- Read `/memories/instructions.md` (behavior rules)
- Based on index + user message, decide which specific files to read

**Memory write rule** (add after line 97):
- After every `write_file` to `/memories/`, also update `/memories/index.md`:
  - New file: add row in corresponding section
  - Updated file: update summary and timestamp in that row
  - Summary requirements: projects/decisions 80-150 chars with data; documents 20-50 chars

### 2. routes.py (upload_pdf endpoint)

After storing PDF content, auto-update `/memories/index.md`:
- Read existing index.md from store (or create template if missing)
- Find "## Documents" section
- Add/update row: `| /documents/{name}.md | {name}, {pages} pages, {method} | {date} |`
- Write back to store

Edge cases:
- index.md doesn't exist: create with empty section headers
- Duplicate filename upload: update existing row, don't duplicate

### 3. No changes to:
- `store.py` (SqliteStore)
- `stream.py` (SSE streaming)
- `main.py` (agent creation)

## Expected Token Usage

- index.md first-turn read: ~300-800 tokens (depends on memory count)
- Current approach (read all files): ~2000+ tokens and growing
- Savings increase as memories accumulate

## Future Extensions (not in scope)

- P2: Memory expiry/compaction (auto-merge old project notes)
- P2: `search_memory` tool for cross-session keyword search
- P3: Bailian RAG integration for semantic memory search
