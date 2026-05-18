# OpenScientist Tools

Available tool categories. Read the full guide before using: `files_cat(path="/global/tools/<file>.md")`

**Important**: These are OpenScientist cloud tools (accessed via MCP). They are separate from your local file tools (Read, Write, Edit, Glob, Grep, Bash).

## Quick Decision Tree

- **Find new papers on a topic** → arxiv (`arxiv__search_papers`)
- **Broad academic search** → openalex (`openalex__search_papers`)
- **Peer reviews & acceptance decisions** → openreview (`openreview__get_reviews`, `openreview__get_decision`)
- **ML models & datasets** → huggingface (`huggingface__search_models`, `huggingface__search_datasets`)
- **Read content of an already-indexed document** → search (`search__search_documents`)
- **Add, list, rename, or delete indexed documents** → source (`source__list_documents`, `source__rename_source`)
- **Create / edit workspace notes** → notes (`notes__create_note`, `notes__edit_note`)
- **Search across notes for specific information** → notes (`notes__search_notes_text`, `notes__search_notes_semantic`)
- **Browse /global/ knowledge base files** → filesystem (`filesystem__ls`, `filesystem__cat`)

## Tool Index

| File | Trigger | Not For | Key Functions | Cost |
|------|---------|---------|---------------|------|
| arxiv.md | discover & download academic papers | broad academic search (use openalex), peer reviews (use openreview) | `search_papers`, `get_paper`, `download_and_index_paper` | medium |
| openalex.md | broad academic paper search and metadata lookup | downloading PDFs (use arxiv), peer reviews (use openreview) | `search_papers`, `get_paper_by_openalex_id` | low |
| openreview.md | peer reviews & acceptance decisions | general paper search (use arxiv/openalex) | `search_paper`, `get_reviews`, `get_decision` | low |
| huggingface.md | find ML models, datasets, paper implementations | paper search (use arxiv/openalex), reviews (use openreview) | `search_models`, `search_datasets`, `get_model`, `get_dataset`, `find_models_for_paper` | low |
| source.md | add, list, rename, or delete indexed documents | querying document contents (use search) | `download_and_index_document`, `list_documents`, `rename_source`, `delete_sources` | low-medium |
| search.md | query content of indexed documents | discovering new papers (use arxiv/openalex), source lifecycle (use source) | `search_documents`, `get_source_content`, `get_source_file` | low |
| notes.md | create/read/edit/search workspace notes | searching indexed documents (use search) | `create_note`, `get_notes_list`, `get_notes_summary`, `search_notes_text`, `search_notes_semantic`, `get_note_chunks_by_ids`, `read_note`, `edit_note`, `append_note`, `delete_note` | low |
| filesystem.md | browse /global/ knowledge base | indexed documents (use search), notes (use notes) | `ls`, `cat`, `grep`, `search` | low |
