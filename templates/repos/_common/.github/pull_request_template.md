## What

<!-- One paragraph. What changes, and why now. -->

## Spec

<!-- specs/NNNN-slug/ -- or "trivial, no spec" with a one-line reason. -->

- Requirements covered:
- Acceptance criteria with passing evidence:

## Verification

<!-- What you actually ran. Paste the result, not a claim that it passed. -->

```
QF_STAGE_ENFORCE=1 sh hooks/stages/run-stage.sh
```

## Risk & reversibility

- Blast radius:
- How to roll back:

## Checklist

- [ ] Traces to a requirement (or explicitly trivial)
- [ ] Every `AC-*` has passing evidence
- [ ] Docs/catalogs updated in this same change
- [ ] No secrets, no real credentials, no company-specific data
