#!/bin/sh
# Regenerate runs: pilot seed 101 (thresholds) + seeds 1-6, both conditions.
# Skips any run whose meta.json already exists. Usage: sh scripts_runall.sh "<backend spec>"
BE="$1"
TAG=$(echo "$BE" | sed 's#/#_#g; s#:#-#')
run() { # $1 condition, $2 seed, $3 dir tag
  [ -f "runs/${TAG}$3/$1_s$2/meta.json" ] && { echo "skip $1 s$2$3"; return; }
  .venv/bin/python -m nullspace.run --condition $1 --seed $2 --tag "$3" --backend "$BE" | tail -1
}
for c in visible blind; do run $c 101 _pilot; done
for s in 1 2 3 4 5 6; do for c in visible blind; do run $c $s ""; done; done
