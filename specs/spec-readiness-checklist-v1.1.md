# Technical Specification Readiness Checklist

**Version** 1.1 · **Status** draft · **Date** 25 September 2026
**Supersedes** v1.0 (Alex Zamurko, Word document, circulated 25 September 2026)
**Author of v1.0** Alex Zamurko · **v1.1 amendments** prepared at his request

A technical specification is workflow-ready when it is sufficiently
authoritative, bounded, deterministic, traceable, and testable for Claude to
derive a conformant implementation plan and for Codex to independently assess
that plan and implementation against the same frozen specification.

> **What changed in v1.1.** Three controls added (TS-47, TS-48, TS-49) and two
> existing items tightened (TS-45, Gate 5). Every v1.0 control keeps its number
> and its wording unless listed in the change log at the end. Numbers are not
> reused or renumbered, because TS-35 requires requirement IDs to be stable and
> a checklist that renumbers itself cannot ask that of anything else.

| ID | Check | Requirement for READY |
|----|-------|----------------------|

## A. Authority & identity

**TS-01 · Specification has a unique identity**
Explicit title, version/revision, status, and date are present.

**TS-02 · Normative authority is explicit**
The document explicitly states whether it is the governing specification for
the implementation target.

**TS-03 · Authority chain is unambiguous**
Superseded, amended, candidate, and governing versions are identified such that
only one effective normative basis exists.

**TS-04 · Normative dependencies are identified exactly**
Every external schema, protocol, registry, taxonomy, Gold Set, baseline, or
other normative dependency is named by exact version or immutable identifier.

**TS-05 · The specification itself can be frozen**
The exact specification artefact can be assigned an immutable
identifier/hash, with no unresolved mutable content determining normative
behaviour.

**TS-47 · Role exclusivity is satisfiable** — *new in v1.1*
No artefact is required to be both a run-level governing pin and a review
target of the same run. An artefact that governs a run must stay
byte-invariant for its duration; an artefact under review must be changeable
to resolve findings raised about it. A specification that requires both of the
same artefact cannot complete a single review cycle.

> Where a document must move between roles, the move is a recorded amendment
> naming reason, affected artefacts, prior set, new set and effective cycle,
> not an edit.

**TS-48 · Enforcement strength of identifiers is stated** — *new in v1.1*
Where this checklist requires an immutable identifier, the specification states
whether that identifier is technically enforced or detection-only in the
target environment.

> A hash under a write boundary the implementing agent does not hold prevents
> substitution. The same hash, where the implementing agent can write both the
> artefact and the checker, detects substitution while the checks run
> faithfully and does nothing otherwise. Both are legitimate; treating the
> second as the first is not. Gate 5 depends on which one is in force.

## B. Scope & boundaries

**TS-06 · Purpose is explicit**
The capability governed by the specification is stated precisely.

**TS-07 · In-scope behaviour is explicit**
Functions, objects, stages, events, inputs, or operations governed by the
specification are identifiable.

**TS-08 · Out-of-scope behaviour is explicit**
Adjacent capabilities that are not governed or must not be implemented under
this specification are identified.

**TS-09 · Inputs are defined**
Required and optional inputs, formats, admissibility conditions, and
provenance requirements are specified.

**TS-10 · Outputs are defined**
Output objects, fields, statuses, allowed values, and failure outputs are
specified.

**TS-11 · Boundary behaviour is governed**
Conditions at the limits of scope have defined outcomes rather than requiring
implementation-level invention.

**TS-49 · Governed surface is sized against the review budget** — *new in v1.1*
The governed surface is bounded such that findings raised against it can
plausibly be resolved within the review cycle budget, or the specification is
explicitly divided into separately reviewable parts.

> A specification can satisfy every other control and still exhaust its cycle
> budget with findings open, which ends the review without a conformance
> outcome. Readiness is not only whether a review can start; it is whether one
> can finish.

## C. Normative rule completeness

**TS-12 · Normative requirements are distinguishable from explanation**
Mandatory rules can be clearly separated from rationale, commentary, notes,
and examples.

**TS-13 · Required behaviour is explicitly specified**
No implementation-required behaviour exists only implicitly in examples,
comments, or explanatory prose.

**TS-14 · Prohibited behaviour is explicit**
Invalid operations, forbidden outputs, and prohibited behaviour have defined
treatment where applicable.

**TS-15 · Normative vocabularies are controlled**
States, event names, relation types, categories, reason codes, and other
closed vocabularies have explicit allowed values or an explicit extensibility
rule.

**TS-16 · Terms have stable operational meanings**
Each implementation-relevant term has one defined meaning across the
specification.

**TS-17 · Rule precedence is explicit**
Where more than one normative rule may apply to the same condition, priority
or conflict resolution is defined.

**TS-18 · Normative consistency is established**
No normative clauses, schemas, examples, or dependent rules prescribe
incompatible behaviour for the same conditions.

## D. Data & object contracts

**TS-19 · Schemas are complete**
Fields, types, cardinality, nullability, required/optional status,
constraints, and defaults are defined.

**TS-20 · Identity rules are explicit**
Object identity, matching, deduplication, merging, replacement, and
supersession rules are defined where applicable.

**TS-21 · Provenance requirements are explicit**
Required source identifiers, spans, hashes, parent objects, evidence links, or
other provenance fields are defined.

**TS-22 · Mutation rules are explicit**
It is clear which data may change, which data is immutable, and under which
operation or event mutation is permitted.

**TS-23 · Canonicalisation rules are defined where representation affects behaviour**
Equivalent input representations cannot generate different normative outcomes
unless explicitly permitted.

## E. State & lifecycle behaviour

**TS-24 · States are explicitly enumerated**
Every valid lifecycle or processing state is defined.

**TS-25 · Legal transitions are explicit**
Valid source-state → event/operation → destination-state transitions are
specified.

**TS-26 · Illegal transitions have defined outcomes**
Attempted invalid transitions produce a specified rejection, error, or no-op
outcome.

**TS-27 · Transition and operation guards are explicit**
Preconditions for state changes or operations are objectively identifiable
from specified inputs/state.

**TS-28 · Terminal and reopening behaviour is explicit**
Terminal states, terminality conditions, and any permitted reopening paths are
defined.

**TS-29 · Execution ordering is explicit where order affects outcome**
Required temporal or procedural sequence is specified independently of rule
precedence.

## F. Determinism & unresolved cases

**TS-30 · Normatively observable outcomes are determined**
For identical governing inputs and state, required observable outcomes are
uniquely determined, or the specification explicitly defines the permitted
outcome set.

**TS-31 · Unresolved-condition behaviour is explicit**
Missing, conflicting, malformed, insufficient, or ambiguous information
resolves to a specified state/output rather than an inferred or guessed
result.

**TS-32 · Multiple-candidate behaviour is explicit**
Where multiple candidates satisfy eligibility conditions, the specification
defines a selection rule, preserves all valid candidates, or returns a defined
unresolved outcome.

**TS-33 · Machine-readable failure outcomes are controlled**
Every implementation-relevant error or failure maps to an enumerated stable
code/category or an explicit extensibility mechanism.

**TS-34 · Human-adjudication boundaries are explicit**
Conditions requiring semantic review or human judgment are identified,
together with the required stop/escalation path.

## G. SPEC → CODE → TEST traceability

**TS-35 · Normative requirements are individually addressable**
Stable requirement IDs, rule IDs, section anchors, or equivalent references
allow precise citation.

**TS-36 · Each material requirement can map to implementation**
Every implementation-relevant normative requirement can be associated with one
or more implementation locations, components, or interfaces.

**TS-37 · Deterministic and semantic requirements are distinguishable**
Requirements reducible to objective machine checks are distinguishable from
requirements requiring semantic review or human adjudication.

**TS-38 · Deterministic requirements have observable acceptance criteria**
Every deterministic requirement has a defined pass/fail condition based on
observable output, state, transition, schema, hash, invariant, or equivalent
evidence.

## H. Conformance & testability

**TS-39 · Conformance cases cover valid, invalid, and boundary behaviour**
The test/conformance set includes positive cases, negative cases, and
edge/boundary cases for each behaviour class where those classes exist.

**TS-40 · Examples are consistent with normative rules**
No example demonstrates behaviour that contradicts the governing normative
clauses.

**TS-41 · Normative tests and illustrative examples are distinguished**
It is explicit which examples are mandatory conformance cases and which are
explanatory only.

## I. Preservation & controlled change

**TS-42 · Preservation and regression requirements are explicit and testable**
Existing behaviour that must remain unchanged is identified together with
evidence or checks capable of detecting regression.

**TS-43 · Permitted implementation change surface is bounded**
Files, modules, interfaces, behaviours, or other implementation surfaces that
may change are distinguished from surfaces that must remain unchanged where
such a boundary is required.

**TS-44 · Compatibility or migration behaviour is defined where affected**
Backward compatibility, version migration, deliberate incompatibility, or
absence of compatibility requirements is explicit.

**TS-45 · Comparison baseline is uniquely identifiable and retrievable**
— *amended in v1.1*
The implementation/data state against which the proposed change will be
assessed has an immutable identifier, **and the artefact that identifier names
can still be obtained.**

> v1.0 required the identifier only. An identifier recorded carefully for an
> artefact that no longer exists still satisfies the original wording, and the
> resulting figures cannot be re-derived by anyone. The identifier is evidence
> that something was pinned; retrievability is what makes it a baseline.

## J. Pre-freeze integrity

**TS-46 · No unresolved material remains before freeze**
No TODO, TBD, comment, annotation, broken cross-reference, unresolved
normative question, or missing dependency can alter implementation-required
behaviour.

## Governing bundle freeze gate

The specification should not enter the implementation workflow until the
complete governing bundle can be frozen. The bundle should contain, as
applicable:

```text
protocol + specification + baseline + Gold Set + schemas + registries
+ taxonomies + normative dependencies
```

Every member of that bundle should have an exact version and/or immutable
identifier such as a SHA-256 hash or commit SHA.

This is distinct from TS-05:

```text
TS-05               can the specification document itself be frozen?
bundle freeze gate  can the entire set of artefacts governing the
                    implementation be frozen?
TS-47               and does any member of that bundle also need to be
                    a review target, which it cannot be?
```

## Final workflow-readiness gate

All five questions should resolve to YES.

**1. Plan derivation** — Can Claude derive a conformant, bounded
implementation plan without inventing normative requirements or independently
resolving unspecified behaviour?

**2. Independent review** — Can Codex determine whether the proposed plan
conforms to the exact frozen specification using the same governing evidence?

**3. Deterministic verification** — Can every requirement classified as
machine-verifiable be mapped to an objective pass/fail check?

**4. Semantic boundary** — Do requirements that cannot be resolved
deterministically have an explicit semantic-review or human-adjudication path?

**5. Reproducibility** — Can the exact governing specification, dependencies,
baseline, and validation artefacts be reconstructed later from immutable
identifiers, **and is the enforcement strength of those identifiers stated?**
— *amended in v1.1, see TS-48*

## Readiness classification

**READY** — all implementation-affecting controls pass and all five final
gates resolve to YES.

**CONDITIONALLY READY** — remaining issues are explicitly non-normative and
cannot change implementation behaviour, expected outputs, tests, state
transitions, or acceptance decisions.

**NOT READY** — at least one unresolved issue could change the required
implementation, required output, deterministic test result, legal state
transition, or conformance judgment.

---

## Change log

### v1.1 — 25 September 2026

Three controls added, two items amended. No v1.0 control was renumbered,
reworded or removed except where listed.

**TS-47 · Role exclusivity is satisfiable.** Added because it is a hard
refusal in the workflow and no v1.0 control covers it. `run_pins.py` enforces
that no artefact is both a run-level governing pin and a review target, on the
grounds that it would have to stay byte-invariant for the run while also being
changeable to resolve findings about it. A specification can satisfy all 46
v1.0 controls and still deadlock on its first cycle.

Observed rather than hypothesised: BOOTSTRAP-002 pinned
`specs/evidence-schema-v1.0.md` as its governing spec while the bootstrap gate
required the same file to be covered by the review target. Its cycle 01 could
therefore review only nine of the ten required components, and the run stopped
there on 17 September. It was resolved on 25 September by a recorded pin
amendment, which is the remedy the note under TS-47 describes.

**TS-48 · Enforcement strength of identifiers is stated.** Added because Gate
5 treats "immutable identifier" as one thing and it is two. Under
`MC1_ENFORCEMENT: CONVENTION_ONLY` the implementing agent holds write access
to the artefacts, the records and the checkers, so a hash is drift detection
that holds while the checks run faithfully. That is a weaker guarantee than
the same hash under a write boundary the agent does not hold. Both are usable;
the difference has to be stated rather than assumed, which is what Gate 5 now
asks.

**TS-49 · Governed surface is sized against the review budget.** Added because
a specification can pass every control and still fail to converge.
BOOTSTRAP-001 reached its cycle ceiling with five findings still open, ending
the review without a conformance outcome on work that would have classified
READY. Scope controls TS-07 and TS-08 bound what is governed; nothing asked
whether the governed surface was small enough to finish.

**TS-45 amended** — "uniquely identifiable" becomes "uniquely identifiable and
retrievable". The citation baseline recorded its implementation SHA carefully
and the implementation itself was not kept, so a digest names an artefact
nobody holds and the figures cannot be re-derived. Recorded in
`specs/gold/PROVENANCE-GAP.md`. The v1.0 wording is satisfied by that state,
which is the gap.

**Gate 5 amended** — reproducibility now also requires the enforcement
strength of the identifiers to be stated. Follows from TS-48.

### Where this version lives

v1.0 was circulated as a Word document. This version is in the repository so
it can be hashed, referenced by exact version, and frozen.

That is not housekeeping. TS-01 requires a unique identity, TS-05 requires the
artefact to be freezable, and TS-04 requires dependencies to be named by exact
version or immutable identifier. A checklist that gates other specifications on
those three controls should satisfy them itself, and a document circulated as
an email attachment satisfies none of them.
