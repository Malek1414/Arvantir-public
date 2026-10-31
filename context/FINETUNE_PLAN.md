# Fine-tuning the re-ranker on Arvana (DGX Spark)

**Goal:** by 16:00 a version of the multilingual MiniLM cross-encoder that ranks leads the way Arvana would, plus a benchmark table **base vs fine-tuned vs LLM vs fixed weights** for the video (the "Tech" 25%).

- Base model: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (118M, multilingual, German works)
- Hardware: DGX Spark (GB10, 128 GB unified memory). Training this model takes minutes, not hours.
- Output: a model folder `models/arvantir-rr-v1/`. Searchify loads it with `RERANKER_MODEL=/path/to/models/arvantir-rr-v1`, nothing else changes.

## Two tasks, one model

| Task | Query | Document | Positive | Negative |
|---|---|---|---|---|
| **A. Lead ranking** (main) | ICP text: seed lead profile or niche description | company profile text | fits the ICP | other niche, too big/small, chain HQ vs shop, directory page itself, dead site |
| **B. Source ranking** (discover) | "a directory listing many {niche} companies in Germany" | search hit title + snippet + first 1,000 chars | member lists, exhibitor lists, partner directories, comparison portals | single company pages, news, blog posts, job boards |

Train both in one run (mixed batches). Task B is cheap to label and makes discover visibly better.

## Data (where the labels come from)

Pipeline runs write every (query, document) pair they score to `data/rank_pairs.jsonl`:

```
{"task": "lead", "niche": "bakeries", "query": "...", "doc": "...", "company_id": "...", "source_url": "..."}
```

Labels, best first:

1. **Arvana's hand sorting (gold).** Ask Stephan or Arne for 30 to 50 leads they sorted by hand for one real customer case (even a screenshot of a Clay table works). This is also the agreement benchmark from Sami's research: "agent sorting doesn't work well, we sort by hand".
2. **Our own quick hand labels (gold).** Sami + Malek label 50 pairs per niche in a tiny label view (fit / maybe / no), 10 minutes per niche.
3. **LLM teacher (silver).** GPT (OpenAI credits) or a Nemotron/Qwen model running on the Spark grades every pair 0–3 with a short reason. Prompt includes Arvana's ICP rules and the 6 niche definitions from the slide. This is distillation: the big model teaches the small fast one, same idea as `searchify-nvidia/minitron/distill.py`.
4. **Hard negatives for free:** companies from niche X used as negatives for niche Y; directory pages as negatives in task A; single company pages as negatives in task B.

Target size: ~3,000–6,000 silver pairs + ~300 gold pairs. Gold is **only for test**, never for training.

## Splits (this is what makes the benchmark honest)

- **Leave-one-niche-out:** train on 5 niches, test on the 6th. Repeat for each niche if time allows, at least for "asset managers" and one small-business niche. This proves the model works on the jury's **surprise niche**.
- Test set = gold labels only.
- Split by company, never by pair (no company in train and test).

## Training (on the Spark)

```
pip install "sentence-transformers>=3" datasets
```

- `CrossEncoder(base, num_labels=1)`, loss: BCE on labels scaled to 0..1 (silver 0–3 → 0, .33, .67, 1), or MultipleNegativesRanking with the hard negatives
- max_length 384, batch 32, lr 2e-5, 2 epochs, warmup 10 %, bf16
- Evaluate every 200 steps on a held-out silver dev set, keep the best checkpoint
- Expected time on GB10: a few minutes per run, so 3–5 runs (lr/epochs) fit

Script: `finetune/train.py` (data in, model folder out), `finetune/bench.py` (model folders in, table out).

## Benchmark (shown in the video)

Systems on the same gold test set:

1. **Fixed weights** (how Arvana's public ICP scorer works: tiers A–D)
2. **LLM pointwise** (GPT grades each lead alone)
3. **mMiniLM base**
4. **mMiniLM fine-tuned on Arvana** (ours)

Metrics:

| Metric | Why |
|---|---|
| NDCG@10, MRR | is the best lead on top |
| Agreement with Arvana's hand sorting (Kendall tau, accuracy fit/no) | the trust question |
| Share sent to "needs a human" at 95 % precision on the rest | how much manual work is left |
| ms per lead, cost per 1,000 leads | fine-tuned MiniLM is ~20 ms and free vs an LLM call per lead |
| Leave-one-niche-out score | works on an unseen niche |

One chart for the video: a bar per system on NDCG@10 and agreement, plus the cost/speed line.

## Timeline

| Time | Who | What |
|---|---|---|
| until 14:30 | pipeline | log every scored pair to `data/rank_pairs.jsonl` (Sami's `rank.py` does this) |
| 14:30–15:00 | Malek / Spark | teacher labels all pairs; Sami + Malek hand-label gold; ask Arvana for a hand-sorted list |
| 15:00–15:40 | Spark | train v1, leave-one-niche-out runs |
| 15:40–16:00 | Spark | `bench.py` → `bench/results.md` + chart; push model folder (or upload to HF private) |
| 16:00 | all | set `RERANKER_MODEL` to v1 for the video run |

**Fallback:** if gold labels are missing, benchmark on silver test with leave-one-niche-out and say so in the video. If training breaks, base mMiniLM stays in the product; the benchmark still shows base vs LLM vs fixed weights.

## Pitch line

"Arvana's agents score each lead alone with fixed weights. We trained a 118M re-ranker on how Arvana sorts. It runs in 20 ms per lead, costs nothing per call, and agrees with their hand sorting X % of the time."
