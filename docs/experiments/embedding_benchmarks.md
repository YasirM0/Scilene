# Embedding Model Evaluation (#143 follow-up)

**Status:** Exploratory research, not wired into the shipped app. Answers the
question the semantic-search epic (#52, #73–81, #101, #113–127) depends on:
*is a real embedding model worth building a semantic layer around, and if so,
which one?*

## Question this answers

`services/recommender.py` and the TF-IDF baseline both currently retrieve
journals by literal keyword overlap (title + subjects + keywords). The #112
benchmark harness already shows that's weak: against the full 55,745-journal
database, the real recommender scores **0.0 recall@5/10/20** and the TF-IDF
baseline scores **3–5% recall@5/10/20** on real published papers
(`benchmark/results/20260808-133549.json`). This experiment checks whether
semantic (embedding-based) retrieval does meaningfully better, and — since a
production app has to actually run inference at request time — which
candidate model gives the best result *for the compute it costs*, not just
the best raw score.

## Method

Full methodology and rationale live as comments in the scripts themselves;
summarized here:

- **Corpus sample, not the full 55,745 journals** — embedding the full corpus
  took over an hour *per model* on this box's 6-core CPU (no GPU). Instead,
  `benchmark/scripts/build_embedding_sample.py` builds a fixed 14,000-journal
  sample (a quarter of the database): every journal referenced as a
  ground-truth target in the #112 benchmark dataset (57 of them, across 166
  query records), plus a seeded random fill. Reused identically across every
  model, so every score is comparable.
- **Two corpus text variants**, via `benchmark/scripts/evaluate_embeddings.py --corpus-variant`:
  - `baseline` — the same (title + subjects + keywords) text the TF-IDF
    baseline and the real recommender already search against.
  - `openalex_topics` — title/subjects/keywords replaced by real OpenAlex
    Topics (`benchmark/scripts/fetch_openalex_topics.py`, up to 10 per
    journal, fetched live from OpenAlex's public Sources API), falling back
    to baseline text for any journal OpenAlex had no match for. No curated
    "index terms" field exists yet (that's #73/#74) — this is a genuine,
    real-data proxy for what that field will eventually provide, not a
    fabricated one. Only 1,298 of the 14,000 sampled journals (~9%) matched
    OpenAlex's index; the rest fell back to baseline text in this variant.
- **Two-stage evaluation** (`benchmark/scripts/run_embedding_matrix.py`) —
  all 6 models × both corpus variants (12 combinations) were first screened
  on a cheap 2,500-journal subset, then the top 3 by quality were re-run on
  the full 14,000-journal sample for authoritative numbers. A 4th combination
  (`snowflake-arctic-embed-m-long`, both variants) was added to the full-scale
  confirmation after screening, since it was both nearly tied for best
  quality **and** by far the fastest — the quality-only cut would have missed
  the actual best speed/quality tradeoff.
- **Scoring**: identical to `benchmark/scripts/evaluate.py` (#112) —
  Recall@5/10/20 and MRR, checking whether each query abstract's real
  journal appears in the model's top-k ranking by cosine similarity.
- **Caveat**: these recall numbers are against the 14,000-journal sample, not
  the full 55,745-journal database the recommender/TF-IDF numbers above were
  computed against. A smaller candidate pool makes recall@k structurally
  easier, so the absolute numbers aren't directly comparable to those two —
  only the embedding models are directly comparable to each other, since all
  of them ran against the identical sample.

## Models tested

**Round 1** (semantic/retrieval-oriented models, similar size class):

| Model | Params | Notes |
|---|---|---|
| `nomic-ai/nomic-embed-text-v1.5` | 137M | English-focused, the original candidate |
| `microsoft/harrier-oss-v1-270m` | 268M | — |
| `Snowflake/snowflake-arctic-embed-m-long` | 137M | Long-context variant (unused here — corpus text is short) |
| `codefuse-ai/F2LLM-v2-160M` | 159M | Instruction-tuned, 200+ language claim |
| `codefuse-ai/F2LLM-v2-80M` | 80M | Smaller sibling of the above; causal/LLM-derived architecture repurposed for embeddings |
| `nomic-ai/nomic-embed-text-v2-moe` | 475M total / 305M active (MoE) | Multilingual (~100 languages) — the only candidate built for it, directly relevant to Scilene's EN/AR/ID UI |

**Round 2** — added after Round 1 showed architecture family matters more than
raw parameter count for CPU speed (F2LLM-80M, the *smallest* Round 1 model,
was slower than 137M-parameter purpose-built encoders). These are
purpose-built small BERT-style encoders, a class specifically known for CPU
efficiency:

| Model | Params | Notes |
|---|---|---|
| `BAAI/bge-small-en-v1.5` | 33M | Asymmetric retrieval (query instruction, no document instruction) |
| `sentence-transformers/all-MiniLM-L6-v2` | 23M | Symmetric — no query/document distinction at all; long-standing "fast baseline" |

## Results — confirmed at full scale (14,000-journal sample)

Sorted by encoding speed (fastest first) — the dimension that matters once a
model has to run at request time, not just once offline:

| Model / corpus | docs/sec | Params | Recall@5 | Recall@10 | Recall@20 | MRR | Total wall time |
|---|---:|---:|---:|---:|---:|---:|---:|
| all-MiniLM-L6-v2 / baseline | **147.6** | 23M | 0.072 | 0.120 | 0.151 | 0.052 | 1.9 min |
| all-MiniLM-L6-v2 / openalex_topics | 104.0 | 23M | 0.102 | 0.127 | 0.157 | 0.064 | 2.5 min |
| bge-small-en-v1.5 / baseline | 74.7 | 33M | 0.120 | 0.151 | 0.241 | 0.089 | 3.8 min |
| bge-small-en-v1.5 / openalex_topics | 52.4 | 33M | 0.133 | 0.157 | 0.223 | 0.097 | 4.8 min |
| **bge-small-en-v1.5 / combined** | 43.4 | 33M | 0.127 | 0.163 | 0.259 | **0.099** | ~6 min |
| arctic-embed-m-long / baseline | 14.5 | 137M | 0.120 | 0.163 | 0.223 | 0.092 | 18 min |
| arctic-embed-m-long / openalex_topics | 9.7 | 137M | 0.114 | **0.175** | 0.223 | 0.094 | 26 min |
| nomic-v2-moe / openalex_topics | 7.9 | 475M | 0.145 | **0.175** | 0.223 | 0.095 | 31 min |
| harrier-270m / baseline | 3.3 | 268M | 0.139 | **0.193** | 0.241 | 0.090 | 76 min |
| harrier-270m / openalex_topics | 1.9 | 268M | 0.114 | 0.163 | 0.229 | 0.078 | 127 min |

`combined` (a new corpus variant, added after the first pass) concatenates
baseline text WITH OpenAlex topics rather than one replacing the other —
richer per-journal document, giving bge-small its best Recall@10 (0.163) and
best MRR (0.099) of any of its own variants, closing about a third of the
gap to arctic-embed-m-long's 0.175 while remaining 3× faster in bulk and at
unchanged single-query latency (corpus text length doesn't affect query
encoding).

harrier-270m/baseline has the single highest recall@10 (0.193), but it's
5.6× slower than bge-small/openalex_topics and 22.6× slower than
all-MiniLM/baseline, for a recall@10 gap that a much cheaper model
(arctic-embed-m-long/openalex_topics, 0.175) already closes most of.
harrier/openalex_topics is dominated outright — worse than its own baseline
variant on every metric, and by far the slowest of everything tested (a
`transformers` warning about unrecognized `rope_parameters` keys for this
model suggests it may be falling back to a slower, less-optimized attention
path on this stack — not investigated further since it isn't the pick
either way). all-MiniLM-L6-v2 is the fastest model tested by a wide margin
but its quality genuinely trails everything else (MRR 0.052–0.064) — the
one candidate here where the speed/quality tradeoff isn't worth it.

## Single-query latency (does the user notice?)

`docs/sec` above measures *bulk corpus-encoding throughput* — a one-time
offline indexing cost, never something a user waits on. What a user actually
experiences is *single-query latency*: how long it takes to embed the one
abstract/tag-list they just typed. These are different things — a model can
be slow in bulk (poor batching efficiency) while still being fast for a
single real-time query. Measured directly (median of 10 runs, batch size 1,
one realistic abstract-length query, warmed up first):

| Model | Single-query latency |
|---|---:|
| all-MiniLM-L6-v2 | 20.2ms |
| **bge-small-en-v1.5** | **39.1ms** |
| arctic-embed-m-long | 130.3ms |
| harrier-270m | 262.2ms |
| nomic-embed-text-v2-moe | 297.0ms |

Human perception of "instant" tops out around 100ms, with "still feels
responsive" extending to roughly 300–1000ms. **Every model tested clears
that bar** — even the slowest (nomic-v2-moe, 297ms) is a small fraction of
a typical page-interaction's total round trip. Notably, harrier's *bulk*
throughput was catastrophic (1.9–3.3 docs/sec) but its single-query latency
is fine (262ms, faster than nomic-v2-moe) — confirms its bulk slowness is a
batching inefficiency, not fundamentally slow per-item compute. Practical
conclusion: since speed is a non-issue across the board at query time, the
real decision is about quality (Recall@10 vs. MRR — see below), with speed
only breaking ties.

## Recall@10 vs. MRR — which matters more for Scilene?

Recall@10 asks "does the right journal appear anywhere in the top 10?" MRR
asks "how close to #1 is it?" (a hit at rank 1 scores 1.0, at rank 10 scores
only 0.1). Scilene shows 10 results per page and is explicitly a
browse-and-compare tool (APC, review speed, quartile, indexing are all
shown so a user can pick the option that fits their constraints), not a
single-answer lookup — that use case leans toward **Recall@10 (or
Recall@20, matching pagination and the "show weaker matches" toggle)**
mattering more than MRR: getting a good candidate onto the page the user
actually sees matters more than whether it's ranked 2nd or 8th within it.
MRR still matters for trust (position bias is real — users weight the top
result disproportionately), so it isn't irrelevant, just secondary for this
particular product shape. This is a product call, not a purely technical
one; the recommendation below optimizes for MRR-with-Recall@10-close-behind,
but if Recall@10 is the priority metric, `arctic-embed-m-long/openalex_topics`
(0.175 vs bge-small/combined's 0.163) is the better pick — still comfortably
under the "user won't notice" latency bar at 130ms.

## Hybrid dense+sparse fusion — tried, didn't help

Fusing bge-small's embedding ranking with the existing TF-IDF baseline's
ranking via Reciprocal Rank Fusion (`benchmark/scripts/evaluate_hybrid_fusion.py`,
RRF, k=60) was tried as another way to raise Recall@10, reusing bge-small's
already-cached corpus embeddings (no re-encoding needed, runs in under a
minute). Result: dense-only 0.175 recall@10 vs. hybrid-fused 0.169 — fusion
made it slightly *worse*. TF-IDF on this corpus is quite weak alone
(recall@10=0.066, MRR=0.035), and RRF weights both rankings equally
regardless of how good each is, so blending in a much weaker signal drags
the strong dense ranking down rather than lifting it. Fusion helps when both
retrievers are independently competitive; here they aren't. Not worth
pursuing further (e.g. down-weighting the sparse side) for the modest
potential gain available.

## Recommendation

**`BAAI/bge-small-en-v1.5`, `combined` corpus variant** (baseline text +
OpenAlex topics concatenated — once #73/#74's real curated index terms
exist, that field should be concatenated the same way, not simply replace
the OpenAlex-topics proxy).

- **Best MRR of every model tested** (0.099 — beats arctic-embed-m-long's
  0.094 and nomic-embed-text-v2-moe's 0.095), while running **~3× faster in
  bulk** than arctic and **~4× faster** than nomic-v2-moe, and comfortably
  the fastest single-query latency (39ms) of the three.
- Smallest model with genuinely competitive quality: 33M params — a quarter
  of arctic-embed-m-long's size, a fourteenth of nomic-v2-moe's.
- Gives up some ground on recall@10 (0.163 vs arctic/nomic's 0.175, ~7%
  relative, down from ~10% before the `combined` corpus improvement) — a
  real, acknowledged tradeoff, not a free win. If recall@10 specifically is
  the binding metric rather than MRR, arctic-embed-m-long/openalex_topics
  remains the better pick (see "Recall@10 vs. MRR" above) — and even then,
  its 130ms single-query latency is still well within "user won't notice."
- Two things that were tried and did NOT beat this: hybrid TF-IDF fusion
  (made recall@10 worse, see above), and going even smaller/faster
  (all-MiniLM-L6-v2 — 2-3× faster still, but its MRR is roughly half of
  bge-small's, a real quality drop, not noise).
- `nomic-embed-text-v2-moe` remains the only genuinely multilingual candidate
  tested — worth reconsidering specifically if/when Arabic- or
  Indonesian-language semantic matching quality becomes the binding
  constraint, since this evaluation's benchmark dataset (built from OpenAlex
  real papers) skews English and doesn't stress-test that axis either way.

## Full Stage 1 screening table (2,500-journal sample, all 12 combinations)

For reference — this is what the full-scale confirmation above was narrowed
down from:

| Model / corpus | docs/sec | Recall@5 | Recall@10 | Recall@20 | MRR |
|---|---:|---:|---:|---:|---:|
| nomic-v2-moe / openalex_topics | 8.3 | 0.265 | 0.337 | 0.434 | 0.186 |
| harrier-270m / openalex_topics | 2.1 | 0.217 | 0.325 | 0.404 | 0.167 |
| harrier-270m / baseline | 3.2 | 0.265 | 0.319 | 0.404 | 0.188 |
| arctic-m-long / baseline | 13.5 | 0.241 | 0.319 | 0.410 | 0.177 |
| arctic-m-long / openalex_topics | 9.1 | 0.259 | 0.319 | 0.410 | 0.182 |
| F2LLM-160M / openalex_topics | 3.0 | 0.241 | 0.313 | 0.380 | 0.147 |
| nomic-v2-moe / baseline | 13.4 | 0.229 | 0.301 | 0.392 | 0.178 |
| F2LLM-160M / baseline | 4.8 | 0.223 | 0.289 | 0.355 | 0.148 |
| nomic-v1.5 / openalex_topics | 9.5 | 0.217 | 0.277 | 0.331 | 0.138 |
| nomic-v1.5 / baseline | 13.1 | 0.181 | 0.253 | 0.337 | 0.127 |
| F2LLM-80M / baseline | 8.6 | 0.133 | 0.199 | 0.271 | 0.102 |
| F2LLM-80M / openalex_topics | 5.4 | 0.157 | 0.199 | 0.307 | 0.114 |

## Raw results

Full per-run JSON reports (all 12 Round 1 screening runs, all 5 Round 1
full-scale confirmations, all 4 Round 2 full-scale runs, the `combined`-corpus
run, the hybrid fusion experiment, and the exact sampled journal IDs used)
are in `benchmark/results/embedding_evaluation_20260812/`.

## What this doesn't answer yet

- Whether *any* of these numbers are good enough in absolute terms to justify
  building #115–127's full pipeline (embedding service, vector store,
  verifier, semantic index builder/importer) — that's a product decision,
  not something this experiment resolves by itself.
- Real curated index terms (#73/#74) may score meaningfully differently than
  the OpenAlex-topics proxy used here — this should be re-run once that
  dataset exists, using the same `--corpus-variant`-style extension point in
  `evaluate_embeddings.py`.
- Arabic/Indonesian retrieval quality specifically — the benchmark dataset's
  query abstracts are predominantly English (built from OpenAlex real
  papers), so this evaluation is not a reliable signal for Scilene's
  non-English search quality one way or the other.
