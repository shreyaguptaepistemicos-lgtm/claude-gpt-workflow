# Reconstructed snapshot

This cycle was frozen before `freeze` preserved the reviewed bytes, so
these copies were reconstructed rather than captured at the time.

Source: git commit `63939ecbe0f5271569bba09a203c8df534612e64`, which the target records as
`protocol_commit`.

Each file below was read from that commit and its SHA-256 compared with
the value recorded in `target.json` at freeze time. All matched. The
recorded hash is what establishes these are the reviewed bytes; the
commit is only where they were found.

```text
98a5920def59c39dc5c8bdbb5700376e21560ee40654173219a5ac0bef246379  specs/evidence-schema-v1.0.md
3d9c570c3a9eb3efcdc2daf1201597af05ad9f20880c74b25f4f607856dcaf60  scripts/validate_cycle.py
5eb8a1a26e21a8876a6778d8e44d73d7a4d890da3b42fa65de6a1e08d3ece7be  scripts/run_review.py
b7eca74ef8b19436907af82c5bb450913b3ba9613200d7b4dcee7260f678ad30  scripts/ledger.py
3e9ba6e2ff769e24473b3ffbebb133d9b1758ae719756f06279f40d59ffa09be  scripts/loop_state.py
941d60adc96f8e3382a1de86bc202419490c82eba7ec0d54d027cec2e6f56540  scripts/bootstrap_gate.py
```

Reconstructed under Alex Zamurko's ruling of 9 September 2026, which
permits revalidation only where the exact bytes can be mechanically
reconstructed and verified, and requires a rerun otherwise.

Cycles frozen after that change carry snapshots taken at freeze time and
need no reconstruction.
