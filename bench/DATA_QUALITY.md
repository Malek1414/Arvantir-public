# Data quality and gold labels (31.10.2026, ~15:00)

Reproducible with `python -m finetune.clean` (data/labels_silver.orig.jsonl -> data/labels_silver.jsonl, report data/clean_report.json).

## 1. Problem
The training data from 13:29 (`data/spark/pairs.jsonl`, 3,624 pairs) contains a lot of non-company junk among the pipeline's own leads:
URL shorteners (bit.ly), adult and betting pages, test-prep blogs, travel and map portals, Thomasnet, apartment listings, and Austrian tax firms for a Germany-only ICP.
The heuristic silver labels still gave these pages 1 to 3 (e.g. all 105 own mechanical-engineering leads = 1).

## 2. Cleaning (`finetune/clean.py`)
Only downgrades to 0, never upgrades, and every change records its rule:

| Rule | Changed |
|---|---|
| portal | 13 |
| host | 335 |
| region | 57 |
| adult | 80 |
| boiler | 33 |
| listing | 1 |
| **Total** | **519 of 3621** |

Check against the final gold labels (n=330):

| | fit vs not-fit agreement | mean abs error (0-3) |
|---|---|---|
| before cleaning | 79.7% | 0.891 |
| after cleaning | 87.9% | 0.376 |

False flags: **0** gold "passt"/"vielleicht" pairs are hit by a cleaning rule.

## 3. Gold labels: two labelers, adjudicated
- Malek labeled 150 pairs (doctors & pharmacies, family offices, real-estate asset managers); Claude labeled the same 150 **blind** and the other 250 (5 niches).
- Agreement Malek vs Claude on the 150: exact 30.7%, Cohen's kappa 0.033 (3 classes), 0.053 (fit vs not). That is close to chance.
  The main pattern: Malek "passt" -> Claude "nein" in 62 cases (e.g. Deloitte, Clifford Chance, PIMCO as real-estate asset managers; test-prep and game sites as medical practices).
- Adjudication rules: agreement -> keep; disagreement and the page is objectively not a company (cleaning rules host/adult/boiler/listing/portal/region) -> "nein" (34x); any other disagreement -> **disputed, not in the test set** (70x, list in `bench/gold_adjudication.json`).
- Final test set: **330 pairs** ({'adjudicated': 34, 'malek+claude': 46, 'claude': 250}).

| Niche | passt | vielleicht | nein |
|---|---|---|---|
| aerzte_apotheken | 0 | 0 | 41 |
| baeckereien_metzgereien | 0 | 0 | 50 |
| family_offices | 0 | 0 | 19 |
| immobilien_asset_manager | 6 | 0 | 14 |
| it_dienstleister | 3 | 4 | 43 |
| maschinenbau | 0 | 0 | 50 |
| steuerberater | 0 | 0 | 50 |
| waschanlagen | 4 | 19 | 27 |

**Consequence for the benchmark:** ranking metrics (NDCG, MRR, tau) are only meaningful for niches with positives: real-estate asset managers, IT service providers and car washes.
The other niches contain only negatives and measure how well a system **rejects junk**. 250 of the 330 labels come from a single labeler (Claude); that is stated in the results.

## 4. Open
- Sami's new data (after the adult filter and portal fixes) is not pushed yet. As soon as it lands in `data/spark/`, the cleaning and the whole training chain rerun automatically.
- The pair_ids in `data/spark/` contain `[tel]` because the phone-number scrubbing also hit the IDs. Consistent within the data; scrub only the `doc` field going forward.


## 5. Update 15:30: map records capped at "vielleicht" (rule `osm_only`)
**Finding in the first benchmark** (`bench/results_clean519.md`, 519-rule labels): on car washes, the fine-tuned model reached only NDCG@10 0.196,
below fixed weights (0.514) and the base model (0.466). The model trained without car washes (LONO) reached 0.799.
**Cause (checked, not guessed):** the fine-tuned model ranks bare OpenStreetMap records at the top ("Waschanlage Charlottenburger Chaussee",
silver label 3). Gold rates these "vielleicht", because operator, site count and contact are unknown. The real operator websites marked
"passt" in gold (Max AutoWasch, Mr. Wash, SB-Waschpark Hamburg) end up lower; the LONO model ranks exactly these near the top.
**Fix:** a lead that is only a map record gets at most 1 ("vielleicht"), the same rule as in gold labeling. 54 labels changed.

| Labels | fit vs not-fit agreement with gold | mean abs error (0-3) |
|---|---|---|
| uncleaned | 79.7% | 0.891 |
| after 519 rules | 87.9% | 0.376 |
| after osm_only too (573 changes) | 94.8% | 0.267 |

Caveat: the jump to 94.8% partly follows by construction, because the rule encodes the same principle as the gold labeler.
The honest test is the benchmark: no gold company is in training. False flags (gold "passt" capped by a rule): 0.
The LONO models (unseen niche) are still on the 519-rule labels; only `arvantir-rr-v1` and the final model are retrained.
