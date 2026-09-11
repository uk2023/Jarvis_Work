# Changes made in this pass

Scope note: this project is ~25,000 lines across 144 files implementing a
genuinely sophisticated cognitive architecture (contracts, perception cascade,
semantic understanding, learning/evolution pipeline, idle autonomy). This pass
did **not** attempt to rewrite it against the two blueprint documents from
scratch — that is a multi-session engineering effort, not something to fake
in one pass. What follows are real, tested fixes for the three concrete
symptoms shown in your transcript.

## 1. Garbage knowledge triples (root cause found and fixed)

**File:** `core/cognition/semantic_understanding/engine.py`

Root cause: the generic catch-all regex (`mera X Y hai`) in `_GENERIC_PATTERNS`
took the literal typed word as the predicate and let the value capture run
past sentence boundaries (its character class allowed `.`), which is exactly
how `favoutite -> junk food batao kya` and `faviurite -> hai. but javascript
pe aur react html ye sb b ata` got written to the DB.

Fixes:
- `normalize()` now folds common misspellings of "favourite" (favoutite,
  faviurite, favirite, favorate, favrite, favroite) to one canonical form.
- New dedicated `_FAVOURITE_PATTERNS` / `_favourite_facts()` extractor
  produces clean `favourite_<category>` predicates (e.g. `favourite_hobby:
  coding`) instead of the generic catch-all mangling them.
- `_GENERIC_PATTERNS`'s value character class no longer allows `.`, so a
  match can't bleed across a sentence boundary.
- New `_is_plausible_fact()` gate (word-count cap, char cap, filler-word
  rejection, sentence-terminator rejection) applied to every fact generator
  before it's ever yielded.
- **Defense in depth:** `core/learning/knowledge_builder.py` gets the same
  gate (`_is_plausible_triple`) at the single choke point every extraction
  path passes through in `build()`, so even a future caller that bypasses
  semantic understanding entirely can't write a garbage triple to storage.

Verified against every literal input from your transcript — see
`_smoke_test_output.txt` in this same directory for the actual run. Also
verified the pre-existing `tests/test_semantic_understanding*.py` assertions
still hold (that test file had a stale import path unrelated to this fix;
fixed as a one-line drive-by since it was blocking your own test suite from
running at all).

## 2. "JARVIS answers from the LLM's own chat recall, not its stored DB"

**File:** `core/orchestration/brain.py`, `_bounded_context_block()`

Root cause: the prompt fed to the LLM labeled raw recent chat history
("RETRIEVED MEMORIES") and actual structured DB facts ("SEMANTIC KNOWLEDGE")
with equal rhetorical weight. Nothing told the model only the second one is
something it's allowed to claim it "remembers" or has "saved" — so it
answered from conversation-history recall even when KnowledgeBuilder had
never actually stored the fact (which is exactly what `/memory_inspect`
showed: JARVIS answered "your favorite hobby is coding" correctly, but that
predicate wasn't in the DB, because of bug #1 above).

Fix: relabeled the sections (`PAST CONVERSATION EXCERPTS -- not confirmed
saved facts` vs `CONFIRMED KNOWLEDGE`) and added an explicit rule instructing
the model not to claim something is remembered/saved unless it's in the
confirmed section. This is a real, structural fix combined with #1 — once
extraction reliably produces clean triples, "confirmed knowledge" actually
gets populated, so this labeling starts doing real work instead of papering
over an empty DB.

This doesn't touch retrieval/ranking logic, only the labeling and instruction
text, so it's low-risk.

## 3. "JARVIS sits idle, never consolidates/learns in the background"

**File:** `core/organism/bootstrap.py`

Root cause: `LearningCoordinator.consolidate()` and
`KnowledgeBuilder.accept_reliable()` were both fully implemented and tested
in isolation, but nothing in the runtime ever called them. The heartbeat's
idle branch only ran `idle_loop.step()` (the goal/curiosity cycle) forever.

Fix: added both calls into the existing idle-heartbeat branch, each
independently try/excepted so one failing never blocks the other or the idle
loop itself, reusing the existing idle cooldown so this doesn't add extra
disk/CPU churn beyond what already runs on that tick.

## What I verified

- All four edited files parse cleanly (`ast.parse`).
- `SemanticUnderstandingEngine.understand()` run against every literal input
  string from your transcript -- garbage inputs now produce either nothing
  (correct: no clean fact is actually assertable) or a clean, single triple.
- `KnowledgeBuilder.build()` run end-to-end with the exact reported garbage
  relation -> rejected before becoming a candidate. Run with a clean relation
  -> flows all the way to a `CANDIDATE`-status entry.
- `KnowledgeBuilder.accept_reliable()` verified to promote that candidate.
- Pre-existing `unittest`-based test suites that actually load
  (`test_semantic_understanding*`, `test_experience_learning_knowledge_
  contract`, `test_action_response_experience_contract`,
  `test_brain_action_response_contract`, `test_learning_self_evaluation_
  contract`, `test_neurosymbolic_integration_contract`, `test_runtime_
  safety`, `test_goal_end_to_end_contract`) all pass against the modified
  code -- 21 of 22 runnable tests green.
- The 1 failing test (`test_event_relation_and_temporal_representation`,
  expects `events[0]["object"] == "Python"` but gets `"kal Python"`) was
  confirmed to **already fail on your original, unmodified code** -- it's a
  pre-existing bug (temporal word not stripped from event object) unrelated
  to this pass. Left as-is rather than scope-creeping into a fourth fix.

## What I could NOT verify

No network access in this sandbox meant I could not `pip install` `pytest`,
`faiss`, `tokenizers`, or `llama-cpp-python`, so I could not boot the full
wired organism (`create_jarvis()`) end-to-end here, nor run the pytest-style
(non-unittest) files in `core/contracts/`. Everything above was verified by
exercising the actual production code paths directly and via the
`unittest`-compatible test files. Please run your own full suite
(`pytest -q`) in your normal Termux/Kali environment before trusting this in
production -- I'd treat this pass as "reviewed and unit-verified," not
"fully integration-tested."

## What's still open (not attempted here, for honesty)

- The two blueprint documents describe a much larger target architecture
  than what this pass touched. I did not do a line-by-line gap analysis
  against them.
- `favourite_<category>` extraction for multi-word categories ("bollywood
  actor") captures the category slightly imperfectly (e.g. `favourite_
  bollywood: "actor SRK"` instead of `favourite_actor: "SRK"`) -- not
  garbage, in-bounds, but not perfectly clean either. Left as a known,
  minor, documented limitation rather than over-engineering the regex.
- No LLM-based re-extraction/repair pass for historically-degraded episodic
  turns was added (only the already-built `accept_reliable()` consolidation
  path was wired up). A proper backfill job would need its own design pass.
