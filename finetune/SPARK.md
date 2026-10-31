# Fine-Tuning auf dem DGX Spark (Malek, ab 14:30)

Alles läuft aus dem Repo-Ordner `Arvantir/`. Reihenfolge: Daten holen, Silber-Labels, Gold-Labels, trainieren, Benchmark, Modell zurück.
Getestet am 31.10. auf dem Mac (MPS) mit Mini-Daten: alle Schritte laufen durch. Auf dem Spark nichts am Code ändern, nur Befehle.

## 0. Setup (5 Min)

```
git clone https://github.com/Malek1414/Arvantir.git && cd Arvantir      # oder git pull
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r finetune/requirements.txt
python -c "import torch;print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"   # muss True + GB10 zeigen
```

Zeigt torch keine GPU (aarch64-Wheel ohne CUDA): im NGC-Container arbeiten, dort ist ein passendes torch drin:

```
docker run --gpus all -it --rm -v "$PWD":/w -w /w nvcr.io/nvidia/pytorch:<aktuelles-tag>-py3 bash
pip install -r requirements.txt -r finetune/requirements.txt
```

## 1. Daten (vom Mac, nicht im Git)

`data/` ist nicht im Repo. Vom Mac rüberkopieren (Sami):

```
rsync -av data/pairs.jsonl data/labels_silver.jsonl data/gold_sample.jsonl data/gold.jsonl data/runs/ <spark>:Arvantir/data/
```

`data/pairs.jsonl` neu bauen geht jederzeit: `python -m finetune.data` (braucht `data/runs/*.json`).

## 2. Silber-Labels (Lehrer)

Variante A, OpenAI (Key nur in `.env`, nie ins Repo):

```
echo "OPENAI_API_KEY=..." >> .env
python -m finetune.label_teacher                 # ~5.000 Paare, ~5 Min, < 2 $
```

Variante B, Modell auf dem Spark selbst (vLLM, OpenAI-kompatibel):

```
vllm serve <z.B. Qwen/Qwen2.5-32B-Instruct oder ein Nemotron> --port 8000 &
OPENAI_BASE_URL=http://localhost:8000/v1 TEACHER_MODEL=<gleicher Name> TEACHER_WORKERS=32 \
  python -m finetune.label_teacher
```

Wichtig: die schwachen Heuristik-Labels vom Mac vorher löschen, sonst werden sie nicht ersetzt:
`rm data/labels_silver.jsonl` (der Lehrer setzt sonst nur fort). Jede Zeile hat `labeler`, so sieht man, wer gelabelt hat.

## 3. Gold-Labels (Sami + Malek, parallel, 10 Min pro Nische)

Auf dem Laptop, nicht auf dem Spark (öffnet einen Browser-Tab auf 127.0.0.1):

```
python -m finetune.label_gold --who=sami  --niche=baeckereien_metzgereien,waschanlagen,it_dienstleister
python -m finetune.label_gold --who=malek --niche=aerzte_apotheken,family_offices,immobilien_asset_manager --port=8766
```

Tasten 1 passt, 2 vielleicht, 3 nein, z zurück. Speichert sofort in `data/gold.jsonl`.
Die Stichprobe (`data/gold_sample.jsonl`) entsteht beim ersten Start und muss **vor dem Training** existieren:
train.py nimmt alle Firmen daraus aus dem Training. Danach `data/gold.jsonl` und `data/gold_sample.jsonl` auf den Spark kopieren.

## 4. Training

```
python -m finetune.train                                   # alle Nischen -> models/arvantir-rr-v1   (~ein paar Min)
python -m finetune.train --lono --niches=immobilien_asset_manager,baeckereien_metzgereien   # mindestens diese zwei
python -m finetune.train --lono                            # alle 6, wenn Zeit ist
```

Defaults nach Plan: max_length 384, batch 32, lr 2e-5, 2 Epochen, warmup 10 %, bf16, Eval alle 200 Schritte, bestes Checkpoint.
Sweep, falls Zeit: `--lr=3e-5 --epochs=3 --out=models/arvantir-rr-v1b`.
Jeder Modellordner hat `arvantir_train.json` (Paare, Labeler, Zeit, eval_loss).

## 5. Benchmark (bis 16:00)

```
python -m finetune.bench                                   # Gold, wenn >= 30 Hand-Labels da sind
python -m finetune.bench --silver                          # Fallback ohne Gold (dann zählt nur die LONO-Zeile)
python -m finetune.bench --models=models/arvantir-rr-v1,models/arvantir-rr-v1b --llm-max=300
```

Systeme: feste Gewichte (Tier A-D), LLM pointwise (nur mit Key/Base-URL, gekappt auf `--llm-max` Paare),
mMiniLM Basis, mMiniLM fine-tuned, fine-tuned ungesehene Nische (LONO). Scores sind rohe Cross-Encoder-Logits
(Sigmoid), nicht der gemischte RR_MIX-Score aus rank.py.
Ausgabe: `bench/results.md`, `bench/results.json`, `bench/chart.png` -> committen und pushen (`git add bench/`).

## 6. Modell zurück in die Pipeline

```
rsync -av <spark>:Arvantir/models/arvantir-rr-v1 ./models/        # models/ ist gitignored, nie pushen
echo "RERANKER_MODEL=$PWD/models/arvantir-rr-v1" >> .env
```

## Wenn etwas bricht

- Kein Gold: Benchmark mit `--silver`, im Video so sagen.
- Training bricht: Basis-mMiniLM bleibt im Produkt, Benchmark zeigt trotzdem Basis vs LLM vs feste Gewichte (`--models=` leer lassen).
- OOM: `--batch=16`. Langsam: `--max-len=256`.
