#!/bin/sh
# Scaffold a new repository from a QuantSmith shape.
#
#   ./templates/repos/scaffold-repo.sh --shape quant-research --into ../my-repo
#   ./templates/repos/scaffold-repo.sh --list
#
# Copies the shared base (_common/), overlays the shape's own directories, and
# drops in that shape's pre-filled quantsmith.conf. The adopter configures
# nothing: the shape already declares its catalogs and which gates block.
#
# Also copies the SDK's gate scripts and spec templates, so the scaffolded repo
# runs its gates immediately rather than after a second manual step.
#
# Deliberately non-destructive: it refuses to write into a non-empty directory.
# Scaffolding is a thing you do once, and silently merging into an existing
# tree is how you get a half-converted repo nobody can reason about.

set -e
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SDK_ROOT=$(CDPATH= cd -- "$SELF/../.." && pwd)

shape=""
into=""

usage() {
  cat <<USAGE
usage: $0 --shape <name> --into <dir>
       $0 --list

shapes:
USAGE
  for d in "$SELF"/*/; do
    n=$(basename "$d")
    [ "$n" = "_common" ] && continue
    [ -f "$d/quantsmith.conf" ] || continue
    desc=$(sed -n '2p' "$d/quantsmith.conf" | sed 's/^# *//' | cut -c1-58)
    printf '  %-16s %s\n' "$n" "$desc"
  done
}

while [ $# -gt 0 ]; do
  case "$1" in
    --shape) shape="$2"; shift 2 ;;
    --into)  into="$2";  shift 2 ;;
    --list)  usage; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

[ -n "$shape" ] && [ -n "$into" ] || { usage >&2; exit 2; }
[ -d "$SELF/$shape" ] || { printf 'No such shape: %s\n\n' "$shape" >&2; usage >&2; exit 2; }

# Refuse to scaffold into an existing tree with content in it.
if [ -d "$into" ] && [ -n "$(ls -A "$into" 2>/dev/null)" ]; then
  printf 'Refusing to scaffold into non-empty directory: %s\n' "$into" >&2
  printf 'Scaffold into a new directory, then move what you need.\n' >&2
  exit 1
fi

mkdir -p "$into"
target=$(CDPATH= cd -- "$into" && pwd)

printf 'Scaffolding %s -> %s\n\n' "$shape" "$target"

# 1. Shared base (dotfiles included -- the . in _common/. matters).
cp -R "$SELF/_common/." "$target/"

# 2. Shape overlay.
[ -d "$SELF/$shape/overlay" ] && cp -R "$SELF/$shape/overlay/." "$target/"

# 3. The shape's config, at the root where every script sources it.
cp "$SELF/$shape/quantsmith.conf" "$target/quantsmith.conf"

# 4. Working gates and spec templates from the SDK, so the repo is runnable now.
mkdir -p "$target/hooks/stages" "$target/templates/spec"
cp "$SDK_ROOT"/hooks/stages/*.sh        "$target/hooks/stages/" 2>/dev/null || true
cp "$SDK_ROOT"/hooks/README.md          "$target/hooks/" 2>/dev/null || true
cp "$SDK_ROOT"/templates/spec/*.md      "$target/templates/spec/" 2>/dev/null || true
cp "$SDK_ROOT"/templates/docs/*.md      "$target/templates/docs/" 2>/dev/null || true
cp "$SDK_ROOT"/instructions/engineering_principles.md \
   "$SDK_ROOT"/instructions/spec_driven_development.md \
   "$target/instructions/" 2>/dev/null || true
chmod +x "$target"/hooks/stages/*.sh "$target"/scripts/*.sh "$target"/.githooks/* 2>/dev/null || true

# 5. Keep empty structural directories in git.
find "$target" -type d -empty -not -path '*/.git/*' -exec touch {}/.gitkeep \;

# 6. A minimal spec index and README so the doc gates have something to read.
[ -f "$target/specs/README.md" ] || cat > "$target/specs/README.md" <<'IDX'
# Specs

Each unit of work lives in `specs/NNNN-slug/` with `spec.md` (WHAT/WHY),
`plan.md` (HOW), and `tasks.md` (WORK). Start from `templates/spec/`, or run
`./scripts/new-spec.sh <slug>`.

## Index

| ID | Feature | Status |
| --- | --- | --- |

**Next free spec number: `0001`**
IDX

cat > "$target/README.md" <<RDM
# <repo name>

<!-- One paragraph: what this repo does, who depends on it, what it is NOT. -->

Scaffolded from the QuantSmith **$shape** shape.

## Quickstart

\`\`\`sh
./scripts/setup-hooks.sh    # wire local git hooks (once)
./scripts/check.sh          # everything CI runs, locally
./scripts/new-spec.sh slug  # start a new unit of work
\`\`\`

## How work happens here

See [docs/working_agreement.md](docs/working_agreement.md). Short version:
trivial changes just get committed; anything else gets a spec, and the roadmap
entry is required before the commit lands.

## Conformance

See [docs/conformance.md](docs/conformance.md) for which parts of the method
this repo has adopted, and [quantsmith.conf](quantsmith.conf) for which gates
block.
RDM

printf '\nDone. %s files.\n\n' "$(find "$target" -type f | wc -l | tr -d ' ')"
cat <<NEXT
Next:
  cd $target
  git init && ./scripts/setup-hooks.sh
  \$EDITOR README.md docs/roadmap.md docs/conformance.md   # fill in the <...>
  ./scripts/check.sh
NEXT
