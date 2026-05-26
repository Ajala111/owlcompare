# Component Spec Template


## Identity

- **Component number:** NN
- **Name:** <human-readable name>
- **Module path:** `src/owlcompare/<path>.py`
- **Roadmap phase:** Phase N
- **Depends on components:** NN, NN
- **Depended on by (planned):** NN, NN

## Purpose

One paragraph. What does this component do? Why does it exist? What's the one-sentence answer to "what would break if we removed it?"

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| ... | ... | ... | ... |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| ... | ... | ... | ... |

## Public API

```python
# Exact signatures of public functions and classes this component exposes.
```

## Internal design

Bullet points or short prose. The key data structures, control flow, and any algorithms worth describing. Keep it concrete enough that a competent engineer can implement from this section alone.

## Edge cases & failure modes

- Case: ... → Behavior: ...
- Case: ... → Behavior: ...

## Acceptance tests

The component is "done" when all of these pass. Write them as test names that will literally exist in the codebase.

- [ ] `test_<thing>_<condition>_<expected>` ...
- [ ] ...

## Out of scope

What this component does *not* do, to prevent scope creep during implementation.

- ...
- ...

## Open questions

Questions to resolve before or during implementation. Each should be answered before the component is marked complete.

- [ ] ...
- [ ] ...

## References

- `docs/ARCHITECTURE.md` § <section>
- `docs/DESIGN_DECISIONS.md` § DD-NNN
- External: <links if any>
