---
name: twitter-bookmarks
description: Sync, search, read, and analyze X/Twitter bookmarks and their linked articles. Installs a local bookmark archive from the user's X account using browser cookies (no API key needed), resolves shortened links to find actual blog posts and papers, and fetches article content on demand. Use this skill when the user mentions bookmarks, saved tweets, wants to find or read articles they bookmarked, explore their reading history, or enrich research with curated social media content. Covers sync, full-text search, link resolution, article reading, LLM classification, and knowledge base generation.
license: MIT
compatibility: Requires Node.js 20+, Python 3.10+, and a logged-in X/Twitter session in Firefox (or Chrome/Brave/Arc on macOS).
metadata:
  skill-author: Fuzzy Dynamics
category: research-tools
---

# Twitter Bookmarks

Sync, search, read, and analyze X/Twitter bookmarks and their linked articles locally.

## Overview

This skill turns X/Twitter bookmarks into a searchable, readable local knowledge base. It solves three problems that the X platform itself doesn't:

1. **Search** -- X has no bookmark search. This skill provides full-text BM25 search across all your bookmarks.
2. **Read articles** -- Most bookmarked tweets link to blogs, papers, or repos via t.co shortened URLs. This skill resolves those links and fetches the actual article content.
3. **Classify and explore** -- LLM or regex-based classification organizes bookmarks by category (tool, research, technique, opinion) and subject domain (ai, biology, finance, etc.).

No X API key or paid tier is required. Authentication uses your existing browser session cookies.

## When to Use This Skill

Use this skill when the user:

- Mentions bookmarks, saved tweets, or X/Twitter content they saved
- Asks to find something they bookmarked ("find that article about context engineering")
- Wants to read a blog post or essay from a bookmarked tweet
- Asks to sync, classify, or explore their bookmarks
- Wants to enrich a research task with relevant content from their reading history
- Asks "what have I been reading about X?" or "what did I save about Y?"

## Quick Start

### Setup (One-time)

1. **Install fieldtheory-cli:**
   ```bash
   npm install -g fieldtheory
   ```

2. **Install helper scripts:**
   ```bash
   # Copy scripts to a directory in your PATH
   cp scripts/ft-sync scripts/ft-resolve scripts/ft-articles ~/.local/bin/
   chmod +x ~/.local/bin/ft-sync ~/.local/bin/ft-resolve ~/.local/bin/ft-articles
   ```

3. **Initial sync:**
   ```bash
   ft-sync
   ```
   This extracts your browser cookies and syncs all bookmarks to a local SQLite database at `~/.ft-bookmarks/bookmarks.db`.

4. **Resolve links (one-time, cached):**
   ```bash
   ft-resolve --all
   ```
   Resolves all t.co shortened URLs to their real destinations and classifies them (article, arxiv, repo, image, video).

### Verify Setup

```bash
ft status          # Check sync status and data location
ft stats           # Collection overview
ft-articles        # List bookmarks with readable article links
```

## Platform Support

| Feature | Linux | macOS |
|---------|-------|-------|
| Sync (Firefox) | Cookie extraction | Native (fieldtheory) + cookie fallback |
| Sync (Chrome/Brave/Arc) | Firefox fallback only | Native (fieldtheory) |
| ft-resolve / ft-articles | Full support | Full support |
| ft classify | Full support | Full support |

**Browser requirement:** You must be logged into x.com in your browser. Firefox is recommended on Linux; on macOS any major browser works.

## Commands Reference

### Syncing

```bash
ft-sync                      # Sync bookmarks (auto-detects browser/platform)
ft-sync --max-pages 10       # Limit pages fetched
ft-sync --continue           # Resume from last cursor
```

### Searching

```bash
ft search <query>            # Full-text BM25 search
ft search "exact phrase"     # Phrase search
ft search "RAG AND agents"   # Boolean operators (AND, OR, NOT)
ft list --limit 20           # Recent bookmarks
ft list --author @omarsar0   # By author
ft list --category research  # By category (after classification)
ft list --domain ai          # By domain (after classification)
ft list --after 2026-01-01   # Date range
ft show <id>                 # Full detail for one bookmark
```

Combine filters: `ft list --category tool --domain ai --author @karpathy --limit 10`

### Resolving Links

```bash
ft-resolve <bookmark_id>     # Resolve t.co links for one bookmark
ft-resolve --all              # Resolve all bookmarks (results cached)
ft-resolve --unresolved       # Only new/unresolved bookmarks
ft-resolve --no-cache         # Force re-resolve everything
```

Output is JSON with each link classified:

```json
{
  "id": "2042520692327895382",
  "author": "rosinality",
  "text": "An information bottleneck analysis on LLM training...",
  "links": [
    {"tco": "https://t.co/1oIxzqPDMF", "url": "https://arxiv.org/abs/...", "type": "arxiv", "domain": "arxiv.org"}
  ]
}
```

Link types: `article`, `arxiv`, `repo`, `image`, `video`, `tweet`, `space`

### Finding Readable Articles

```bash
ft-articles                   # All bookmarks with article/paper/repo links
ft-articles --topic "agents"  # Filter by keyword in tweet text
ft-articles --arxiv           # Only arxiv papers
ft-articles --repos           # Only GitHub/GitLab repos
ft-articles --json            # Machine-readable output
ft-articles --limit 20        # Limit results
```

### Reading Article Content

After finding a bookmark's article URL via `ft-resolve` or `ft-articles`, fetch the content using your platform's HTTP tool:

| Platform | Command |
|----------|---------|
| Claude Code | `WebFetch(url, prompt)` |
| Gemini CLI | `web_fetch(url)` |
| Windsurf | `read_url_content(url)` |
| Fallback | `curl -sL <url>` via Bash |

### Classifying

```bash
ft classify --regex           # Fast regex classification (instant, no LLM cost)
ft classify                   # LLM classification (uses claude or codex CLI)
ft classify-domains           # Classify by subject domain only
ft categories                 # Show category distribution
ft domains                    # Show domain distribution
```

Categories: `tool`, `technique`, `research`, `opinion`, `launch`, `security`, `commerce`

### Exploring

```bash
ft stats                      # Top authors, languages, date range
ft viz                        # Terminal sparkline dashboard
ft sample research            # Random sample from a category
```

### Knowledge Base

```bash
ft wiki                       # Build interlinked wiki from bookmarks
ft ask "what tools for RAG?"  # Query the wiki (lexical, no embeddings)
ft ask "question" --save      # Save answer as a concept page
ft md                         # Export bookmarks as individual markdown files
ft lint                       # Check wiki for broken links
```

## Core Workflow: Search -> Resolve -> Read

When the user wants to read an article they bookmarked:

1. **Search** for the bookmark:
   ```bash
   ft search "context engineering"
   ```

2. **Resolve** the t.co links to find the real article URL:
   ```bash
   ft-resolve <bookmark_id>
   ```

3. **Read** the article content using your platform's HTTP fetch tool on the resolved URL.

4. **Summarize** and connect the content to the user's current work.

When the user wants to browse all their bookmarked articles:

1. **List** articles:
   ```bash
   ft-articles --topic "LLM agents"
   ```

2. **Selectively read** the most relevant ones via HTTP fetch.

3. **Synthesize** across multiple articles if the user needs a comprehensive view.

## How It Works

### Authentication

The skill uses your existing browser session -- no API keys or paid X tier needed. It reads cookies (`ct0` and `auth_token`) directly from your browser's cookie database:

- **macOS:** fieldtheory's native extraction works for Chrome, Brave, Arc, Firefox. Falls back to manual Firefox cookie extraction if native fails.
- **Linux:** Manual Firefox cookie extraction (reads `~/.mozilla/firefox/*/cookies.sqlite`).

### Data Storage

Everything is local:

- **Database:** `~/.ft-bookmarks/bookmarks.db` (SQLite with FTS5 full-text search)
- **Raw cache:** `~/.ft-bookmarks/bookmarks.jsonl`
- **Resolved links:** `~/.ft-bookmarks/resolved-links.json`
- **Wiki:** `~/.ft-bookmarks/md/` (markdown files)

### Link Resolution

Most bookmarked tweets contain t.co shortened URLs. `ft-resolve` follows the HTTP redirect to get the real URL, then classifies it:

- `twitter.com/.../photo/*` -> `image`
- `twitter.com/.../video/*` -> `video`
- `arxiv.org/*` -> `arxiv`
- `github.com/*` or `gitlab.com/*` -> `repo`
- `youtube.com/*` -> `video`
- Everything else -> `article`

Results are cached in `resolved-links.json` so subsequent runs are instant.

## Troubleshooting

### "Couldn't connect to your browser session"

You're not logged into x.com in Firefox (Linux) or any supported browser (macOS). Log in and retry.

### Sync works but gets 0 new bookmarks

Your cookies may have expired. Re-login to x.com in your browser and run `ft-sync` again.

### ft-resolve hangs or is slow

Each t.co link requires an HTTP HEAD request. For 165 bookmarks with ~120 links, expect ~2 minutes on first run. Subsequent runs use the cache and are instant.

### ft-articles shows "No resolved links found"

Run `ft-resolve --all` first to populate the link cache.

## Integration with Other Skills

### Literature Review

1. Use `ft-articles --arxiv` to find papers you bookmarked
2. Feed the arxiv IDs to `paper-lookup` for full metadata
3. Use `ft search` to find related bookmarks by topic

### Research Lookup

1. Search bookmarks for context on a research question
2. Cross-reference with `perplexity-search` or `paper-lookup` for deeper coverage
3. Use bookmarked expert opinions to frame research direction

### Scientific Writing

1. Find relevant bookmarks to cite or reference
2. Read the linked articles for background material
3. Use `ft ask` to query your bookmark knowledge base

## Dependencies

### Required

- **Node.js 20+** -- for fieldtheory-cli
- **Python 3.10+** -- for helper scripts (ft-sync, ft-resolve, ft-articles)
- **curl** -- for t.co link resolution
- **fieldtheory-cli** -- `npm install -g fieldtheory`

### Optional

- **claude CLI** or **codex CLI** -- for LLM classification (`ft classify`)

## Bundled Scripts

| Script | Purpose |
|--------|---------|
| `scripts/ft-sync` | Cross-platform bookmark sync with automatic cookie extraction |
| `scripts/ft-resolve` | Resolve t.co links to real URLs with type classification |
| `scripts/ft-articles` | Filter bookmarks to only those with readable article links |

See `references/setup.md` for detailed installation instructions and `references/link-types.md` for link classification details.
