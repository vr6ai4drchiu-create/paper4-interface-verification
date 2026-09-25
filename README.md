# Bounding the Human Interface in Clinical AI Safety Arguments: What Verification Cannot See

Data and analysis code for the fourth report in a series on confining decision authority in a
deployed clinical AI system.

**Lu-An Chiu, MD** · ORCID [0009-0003-2165-0950](https://orcid.org/0009-0003-2165-0950)

---

## What this repository is

The adversarial harness, the per-trial records, and the analysis that produces every table and
figure in the paper.

```
harness/            the adversarial harness (redacted, see below)
results/            one JSONL record per trial · 8 runs · 94,036 trials · ~30 MB
analysis/           recompute every reported figure from results/
governed_tokens.json   the tokens that stand in for the withheld clinical vocabulary
```

## Reproducing the paper

```bash
python analysis/verify_released_dataset.py
```

It recomputes every quantity in Sections 4 and 5 from `results/` alone and compares each one
against the value printed in the paper. It exits non-zero if any figure moves.

The study itself: 94,036 adversarial trials, four model families from three vendors, each run
twice — once with the architectural bound disabled, once enabled. With the bound enabled, none
of the 21,123 distinct ungoverned labels reached the kernel and none altered a decision.

## Field semantics — read this before analysing

Two fields measure different things and are easy to conflate:

| Field | Meaning | Endpoint |
|---|---|---|
| `new_invented` | ungoverned label strings the attacking model produced | **coverage**; populated under both conditions |
| `ungoverned_reached_kernel` | of those, the ones passed into kernel construction | **the bound**; necessarily empty when the bound is on |

Coverage figures derive from the first. The N → 0 result derives from the second. Using the
second for coverage yields the spurious conclusion that the bound-enabled condition has zero
coverage.

## Redaction — two things, and nothing else

**1. Protected identifiers.** The protected-identifier guard's self-test fixtures contain real
identifiers held locally on the author's machine. They are replaced by `<...-REDACTED>`
placeholders. The guard's logic is unmodified.

No patient data of any kind was available to the attack path. Every value transmitted to any
vendor was drawn from `harness/synthetic_seeds.json`. Isolation was enforced by **allowlist**,
not denylist: only strings traceable to that corpus could be transmitted, and every payload was
additionally screened for record-number, national-identifier and telephone patterns before
leaving the process. A match raised and aborted the trial rather than warning and continuing.

**2. The governed clinical vocabulary.** The set of clinical labels the deployed system governs
is **not released**. In `results/` and in `harness/synthetic_seeds.json` it appears as stable
tokens:

| Token | Meaning |
|---|---|
| `<GOV-nn>` | a governed term |
| `<GOV-nn~vk>` | an attacker string that resolves to a governed term |
| `<GOV-nn~wsk>` | one that resolves only after internal whitespace is stripped |

One member, `PCOS`, is left verbatim. Section 5 of the paper is unreadable without a concrete
term — its central finding is that 346 of 359 decision-altering strings were *writing variants
of a governed term*, and a reader cannot judge that without seeing what they are variants of.
`PCOS` is a standard international abbreviation, so naming it discloses one membership fact and
nothing about the set's composition.

**No logic is altered by either redaction**, and that the released records still reproduce every
reported figure was verified rather than assumed — see the command above.

## Licence

CC BY-NC-ND 4.0, consistent with the earlier reports in this series.
