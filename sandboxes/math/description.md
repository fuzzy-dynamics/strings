# Math (Lean 4)

A sandbox carrying the Lean 4 toolchain via `elan` — `lean`, `lake`, and `elan` itself are on `PATH`. Based on the `leanprovercommunity/lean4:latest` image.

Use this for theorem proving, Mathlib work, or any Lean-first computation the host doesn't have installed.

**Size:** ~400 MB (pulls the base Lean 4 layer; Mathlib cache is populated on first `lake update` / `lake build`).

**Contents:**
- Lean 4 (latest stable via elan)
- Lake build tool
- elan toolchain manager

**Typical workflow:**

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/sandbox-use/scripts
bash $SCRIPTS/activate.sh math
bash $SCRIPTS/exec.sh --command 'lake new my-project math'
bash $SCRIPTS/exec.sh --command 'cd my-project && lake build'
```

Mathlib is not pre-cached — the first `lake update` in a project will download it. If you need pre-cached Mathlib, build a derivative image later (SPEC follow-up).

**Not suitable for:** Python scientific stack, SymPy, SageMath — those need their own sandbox.
