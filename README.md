# Café Poliçe: an open motor-insurance pricing engine (freMTPL2)

[![License: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)

Code, results and the Turkish article *"Bir Yılın Faturasını On Hasar Yazar"* (Café Poliçe) for a frequency × severity pricing engine with an Extreme Value Theory large-loss layer, built on the open **freMTPL2** French motor third-party-liability portfolio.

Model on Hugging Face: [makactuary/fremtpl2-pricing-engine](https://huggingface.co/makactuary/fremtpl2-pricing-engine)

## Data

`freMTPL2freq` and `freMTPL2sev` (OpenML 41214 / 41215, **CC0**) from CASdatasets by C. Dutang and A. Charpentier: 678,013 policies, 358,360 policy-years, 26,406 claims after cleaning. Downloaded at run time into `data/` (git-ignored).

Cleaning, all stated in the article: exposure capped at one year (1,224 records), claim counts capped at 4, and 9,116 policies with a claim count but no recorded amount treated as claim-free (as in the scikit-learn example on this dataset).

## Engine and results (20% hold-out, 135,603 policies)

| Component | Method | Result |
|---|---|---|
| Frequency | Poisson GLM vs Poisson gradient boosting (exposure-weighted) | Gini 0.273 vs **0.321**; D² 4.1% vs **6.2%** |
| Attritional severity | Gamma GLM on per-claim cost capped at the 99th percentile (€16,024) | |
| Large losses | Generalised Pareto on 199 excesses over €16,024 | ξ = 0.87, bootstrap 95% CI 0.59–1.11; 19.8% of resamples have ξ ≥ 1 |
| Pure premium | frequency (GBM) × (Gamma + large-loss load) | Gini 0.331; predicted / observed **0.999** with the empirical load (€680 per claim), 1.233 with the GPD load (€1,210) |
| Benchmark | single Tweedie GLM (p = 1.9) | Gini 0.273; predicted / observed 0.984 |

The ten largest claims made up 20.8% of the test year's claim cost, the hundred largest 41%. The large-loss load is a risk-appetite choice, not a statistical result: the tail is too heavy for its mean to be estimated tightly.

## Run

```bash
pip install -r requirements.txt
python -c "import sys; sys.path.insert(0,'src'); from pathlib import Path; from pricing import run; run(Path('data/openml'), Path('outputs'))"
python article/build_article.py        # rebuilds the article (.docx, .md) from outputs/
python -m pytest tests -q
```

## Contents

| Path | |
|---|---|
| `src/pricing.py` | Loading, cleaning, frequency / severity / EVT models, Gini and evaluation |
| `outputs/metrics.json`, `outputs/evt_uncertainty.json` | All reported numbers |
| `outputs/charts/` | The six article charts (Turkish labels) |
| `article/` | Article as .docx, .pdf and .md, and the script that builds it |

## Limitations

French data from a single period; no claims inflation, IBNR or reinsurance. The large-loss model rests on 199 claims. Results illustrate a method and are not a tariff for the Turkish market.

## Licence

Code: MIT. Data: CC0 (CASdatasets via OpenML), not redistributed here.
