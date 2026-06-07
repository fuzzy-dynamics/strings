# Domain Playbook: Extremal Graph Theory

Use for Turán/Ramsey/coloring/matching/connectivity/subgraph-forcing problems.

## First Objects To Test

- complete graphs,
- complete multipartite graphs,
- random graphs,
- cycles and paths,
- bipartite extremal graphs,
- sparse regular graphs,
- blow-ups,
- critical graphs,
- incidence/projective graphs.

## Theorem Families

- Turán and Erdős-Stone-Simonovits,
- Ramsey bounds,
- Hall/Kőnig/Menger/max-flow min-cut,
- Brooks/degeneracy/list-coloring tools,
- dependent random choice,
- graph containers,
- spectral extremal bounds,
- regularity/removal lemmas,
- probabilistic method.

## Common Barriers

- random graph lower bounds,
- complete multipartite sharpness,
- local degree condition not forcing global structure,
- constant-loss in regularity/container methods,
- small critical obstructions,
- spectral bound too weak by a logarithm or constant.

## First Experiments

- enumerate graphs for small `n`,
- search for forbidden-subgraph witnesses,
- test random graphs at predicted thresholds,
- minimize counterexamples by edge/vertex deletion,
- compute degree sequence, clique number, independence number, chromatic number when feasible.

## Product Ladder

1. finite counterexample to a stronger variant,
2. small exact threshold,
3. special case for bipartite/regular/triangle-free graphs,
4. structural lemma for minimal counterexample,
5. asymptotic bound with explicit loss,
6. reduction to a known extremal theorem.

## Induced Trees In Triangle-Free High-Chromatic Graphs

Use this sub-playbook for problems of the form:

```text
triangle-free + high/infinite chromatic number -> induced copy of a fixed tree
```

Status discipline:

- If "tree" includes infinite trees, test the disjoint-union obstruction first.
- If "tree" means fixed finite tree, treat the general statement as the triangle-free Gyarfas-Sumner frontier unless a stronger source settles the exact tree family.
- Do not stop at this classification for a prove/disprove run; launch a Lovasz campaign against the actual missing lemmas.

Actual lemma queue seeds:

1. **Private-neighbor leaf-extension lemma:** given an induced copy of `T - leaf`, find a neighbor of the attachment vertex anticomplete to the rest of the embedded tree.
2. **Chromatic reservoir lemma:** after embedding a partial induced tree, preserve an infinite/high-chromatic reservoir avoiding forbidden chords.
3. **Neighborhood hypergraph lemma:** encode bad chords as a hypergraph covering problem and find a high-chromatic residual set.
4. **Minimal obstruction lemma:** characterize finite triangle-free high-chromatic graphs omitting a fixed small tree such as a path, broom, radius-2 tree, or radius-3 tree.
5. **Compactness reduction lemma:** formalize the finite chi-bounding equivalence using de Bruijn-Erdos compactness and disjoint union.

Required worker routes:

- `COUNTEREXAMPLE`: search finite triangle-free graphs omitting specific small trees; include Mycielski, high-girth, bipartite blow-up, and critical graph families.
- `MINER`: mine induced-tree patterns in Mycielski/high-girth/random triangle-free samples.
- `COMPUTATION`: test private-neighbor extension failures and minimal obstruction certificates.
- `SKEPTIC`: verify that any alleged obstruction really omits the target induced tree and remains triangle-free/high-chromatic for the claimed bound.
- `FORMALIZER`: formalize compactness/disjoint-union reductions and known easy cases when possible.

Ontology pivots after two native failures:

- graph coloring -> neighborhood hypergraphs,
- induced tree embedding -> constraint satisfaction/SAT obstruction,
- triangle-free graph -> spectral expansion or adjacency algebra,
- chromatic reservoir -> finite set systems/transversal lemmas.

Acceptable outputs:

- verified compactness/disjoint-union reduction,
- checked finite counterexample search with exact bounds,
- verified special tree family,
- obstruction family,
- failed actual-lemma attack with two direct attacks and next exact attempt,
- still open after full Lovasz campaign ledger.

Deterministic tools:

```bash
GRAPH="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/finite_graph_backend.py)"
python3 "$GRAPH" --n 6 --triangle-free --tree path:4 --omit-induced-tree --min-chromatic 3 --limit 20

MINER="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/empirical_miner.py)"
python3 "$MINER" --domain graphs --graph-family mycielski --iterations 3
python3 "$MINER" --domain graphs --graph-family cycles --max-n 20

CAMPAIGN="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_campaign_template.py)"
python3 "$CAMPAIGN" --template induced-tree-triangle-free
```

Use `finite_graph_backend.py` before claiming a finite answer for a small tree. It computes triangle-freeness, exact chromatic number, and exact induced-tree containment on the enumerated graph scope. A negative bounded search is not a theorem, but it is required counterexample pressure for any new lemma.

For the finite/infinite equivalence route, hand Generator one of these WIT templates instead of free-form prose:

- `../references/examples/compactness_disjoint_union_reduction.wit`
- `../references/examples/finite_chi_bounding_compactness_template.wit`

These templates formalize only the reduction skeleton. They do not settle the triangle-free Gyarfas-Sumner frontier without a verified finite chi-bound or verified obstruction family.
