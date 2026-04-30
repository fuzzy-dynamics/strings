# OpenScientist Tools

Available tool categories. Read the full guide before using: `files_cat(path="/global/tools/<file>.md")`

**Important**: These are OpenScientist cloud tools (accessed via MCP). They are separate from your local file tools (Read, Write, Edit, Glob, Grep, Bash).

## Quick Decision Tree

- **Find new papers on a topic** → arxiv (`arxiv__search_papers`)
- **Citation / reference graphs** → openalex (`openalex__get_citations`, `openalex__get_references`)
- **Peer reviews & acceptance decisions** → openreview (`openreview__get_reviews`, `openreview__get_decision`)
- **ML models & datasets** → huggingface (`huggingface__search_models`, `huggingface__search_datasets`)
- **Read content of an already-indexed document** → search (`search__search_documents`)
- **Annotate sections of indexed docs** → annotation (`annotation__add_annotation`)
- **Create / edit workspace notes** → notes (`notes__create_note`, `notes__edit_note`)
- **Search across notes for specific information** → notes (`notes__search_notes`)
- **Convert a PDF URL into a readable note** → notes (`notes__pdf_to_note`)
- **Browse /global/ knowledge base files** → filesystem (`filesystem__ls`, `filesystem__cat`)

## Tool Index

| File | Trigger | Not For | Key Functions | Cost |
|------|---------|---------|---------------|------|
| arxiv.md | discover & download academic papers | citation graphs (use openalex), peer reviews (use openreview) | `search_papers`, `get_paper`, `search_by_author`, `download_and_index_paper` | medium |
| openalex.md | citation graphs, references, related papers | downloading PDFs (use arxiv), peer reviews (use openreview) | `search_papers`, `get_paper`, `get_references`, `get_citations`, `find_related` | low |
| openreview.md | peer reviews & acceptance decisions | general paper search (use arxiv/openalex) | `search_paper`, `get_reviews`, `get_decision` | low |
| huggingface.md | find ML models, datasets, paper implementations | paper search (use arxiv/openalex), reviews (use openreview) | `search_models`, `search_datasets`, `get_model`, `get_dataset`, `find_models_for_paper` | low |
| search.md | query content of indexed documents | discovering new papers (use arxiv/openalex) | `search_documents`, `get_source_content`, `get_document_structure` | low |
| annotation.md | annotate sections of indexed documents | standalone notes (use notes), general search (use search) | `add_annotation`, `get_annotations` | low |
| notes.md | create/read/edit/search workspace notes, convert PDFs to notes | searching indexed documents (use search) | `create_note`, `read_note`, `edit_note`, `append_note`, `delete_note`, `search_notes`, `pdf_to_note` | low-medium |
| filesystem.md | browse /global/ knowledge base | indexed documents (use search), notes (use notes) | `ls`, `cat`, `grep`, `search` | low |
