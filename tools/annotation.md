# Annotation

## Meta
trigger: annotate sections of indexed documents with notes, reviews, or connections
not_for: editing workspace notes (use notes tool), general search (use search tool)
cost: low
tools: annotation__add_annotation, annotation__get_annotations

## When to Use
- User wants to annotate a specific section of an indexed paper or document
- Adding review comments, definitions, cross-references, or code snippets to sections
- Retrieving existing annotations for a source
- NOT for standalone notes (use notes tool)

## Functions

### annotation__add_annotation
Add an annotation to a document section.
params:
  - source_id (str, required): source/paper ID
  - section_title (str, required): section title from ToC (e.g. "Abstract", "1.1 Background")
  - annotation_type (str, required): one of: citation, review, definition, connection, code, note
  - content (str, required): annotation text
  - citations (list[str], optional): citation references

### annotation__get_annotations
Get all annotations for a source.
params:
  - source_id (str, required): source/paper ID

## Examples

run(tool="annotation__add_annotation", params={
  "source_id": "abc123",
  "section_title": "3.1 Architecture",
  "annotation_type": "note",
  "content": "This is similar to the approach in ResNet"
})
run(tool="annotation__get_annotations", params={"source_id": "abc123"})
