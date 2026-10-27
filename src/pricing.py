"""Motor third-party liability pricing engine on freMTPL2 (frequency x severity + EVT large losses).

Data: freMTPL2freq / freMTPL2sev (OpenML 41214 / 41215, CC0), from CASdatasets
(Dutang & Charpentier, 2018), associated with "Computational Actuarial Science with R".

Pipeline
1. Clean: cap exposure at 1 year and claim counts at 4; policies with a claim count
   but no recorded amount are treated as claim-free (as in the scikit-learn example).
2. Frequency: Poisson GLM vs Poisson gradient boosting, exposure as weight.
3. Severity: per-claim cost split at a large-loss threshold u; attritional part by a
   Gamma GLM, excess over u by a Generalised Pareto distribution (EVT), loaded per claim.
4. Pure premium = frequency x severity, compared with a single Tweedie GLM.
5. Hold-out evaluation (20% of policies): deviance, Gini (Lorenz), calibration by decile.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import GammaRegressor, PoissonRegressor, TweedieRegressor
from sklearn.metrics import mean_gamma_deviance, mean_poisson_deviance, mean_tweedie_deviance
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, KBinsDiscretizer, OneHotEncoder, OrdinalEncoder, StandardScaler

SEED = 42
CATS = ["VehBrand", "VehPower", "VehGas", "Region", "Area"]
BINNED = ["VehAge", "DrivAge"]


def load(data_home: Path) -> pd.DataFrame:
    from sklearn.datasets import fetch_openml
    freq = fetch_openml(data_id=41214, as_frame=True, data_home=str(data_home), parser="auto").frame
    sev = fetch_openml(data_id=41215, as_frame=True, data_home=str(data_home), parser="auto").frame
    freq["IDpol"] = freq["IDpol"].astype(int)
    sev = sev.assign(IDpol=sev["IDpol"].astype(int)).groupby("IDpol")["ClaimAmount"].sum()
    df = freq.set_index("IDpol").join(sev).fillna({"ClaimAmount": 0.0})
    df["VehGas"] = df["VehGas"].astype(str).str.strip("'")
    for col in CATS:
        df[col] = df[col].astype(str)
    return df


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report = {"policies": int(len(df)), "exposure_capped": int((df["Exposure"] > 1).sum()),
              "claimnb_capped": int((df["ClaimNb"] > 4).sum()),
              "claims_without_amount": int(((df["ClaimNb"] > 0) & (df["ClaimAmount"] == 0)).sum())}
    df = df.copy()
    df["Exposure"] = df["Exposure"].clip(upper=1)
    df["ClaimNb"] = df["ClaimNb"].clip(upper=4)
    df.loc[(df["ClaimAmount"] == 0) & (df["ClaimNb"] >= 1), "ClaimNb"] = 0
    df["Frequency"] = df["ClaimNb"] / df["Exposure"]
    df["AvgClaim"] = np.where(df["ClaimNb"] > 0, df["ClaimAmount"] / df["ClaimNb"].clip(lower=1), 0.0)
    df["PurePremium"] = df["ClaimAmount"] / df["Exposure"]
    report.update(claims=int(df["ClaimNb"].sum()), total_exposure=float(df["Exposure"].sum()),
                  portfolio_frequency=float(df["ClaimNb"].sum() / df["Exposure"].sum()),
                  total_claim_amount=float(df["ClaimAmount"].sum()))
    return df, report


def glm_features() -> ColumnTransformer:
    return ColumnTransformer([
        ("binned", KBinsDiscretizer(n_bins=10, subsample=None, quantile_method="averaged_inverted_cdf"), BINNED),
        ("onehot", OneHotEncoder(handle_unknown="ignore"), CATS),
        ("bm", "passthrough", ["BonusMalus"]),
        ("density", make_pipeline(FunctionTransformer(np.log), StandardScaler()), ["Density"]),
    ], remainder="drop")


def gbm_features() -> ColumnTransformer:
    return ColumnTransformer([
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CATS),
        ("num", "passthrough", BINNED + ["BonusMalus", "Density"]),
    ], remainder="drop", verbose_feature_names_out=False)


def gini(y_true: np.ndarray, y_pred: np.ndarray, weight: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Exposure-weighted Lorenz curve ranked by predicted risk; Gini = 1 - 2 * area (higher = better ranking)."""
    order = np.argsort(y_pred)
    w, loss = weight[order], (y_true * weight)[order]
    cum_w = np.r_[0, np.cumsum(w)] / w.sum()
    cum_loss = np.r_[0, np.cumsum(loss)] / loss.sum()
    return float(1 - 2 * np.trapezoid(cum_loss, cum_w)), cum_w, cum_loss


def fit_gpd(excess: np.ndarray) -> dict:
    shape, _, scale = stats.genpareto.fit(excess, floc=0)
    return {"xi": float(shape), "sigma": float(scale), "n": int(len(excess)),
            "mean_excess_model": float(scale / (1 - shape)) if shape < 1 else float("inf")}


def run(data_home: Path, out_dir: Path) -> dict:
    df, cleaning = clean(load(data_home))
    train, test = train_test_split(df, test_size=0.2, random_state=SEED)
    w_tr, w_te = train["Exposure"].to_numpy(), test["Exposure"].to_numpy()
    res: dict = {"cleaning": cleaning, "train_policies": int(len(train)), "test_policies": int(len(test))}

    # 1. frequency
    mean_freq = np.average(train["Frequency"], weights=w_tr)
    freq_models = {
        "poisson_glm": make_pipeline(glm_features(), PoissonRegressor(alpha=1e-4, max_iter=1000)),
        "poisson_gbm": make_pipeline(gbm_features(), HistGradientBoostingRegressor(
            loss="poisson", max_leaf_nodes=63, learning_rate=0.05, max_iter=600, early_stopping=True,
            validation_fraction=0.1, n_iter_no_change=30, categorical_features=list(range(len(CATS))), random_state=SEED)),
    }
    freq_pred, res["frequency"] = {}, {}
    null_dev = mean_poisson_deviance(test["Frequency"], np.full(len(test), mean_freq), sample_weight=w_te)
    for name, model in freq_models.items():
        fit_kw = {f"{model.steps[-1][0]}__sample_weight": w_tr}
        model.fit(train, train["Frequency"], **fit_kw)
        p = model.predict(test)
        dev = mean_poisson_deviance(test["Frequency"], p, sample_weight=w_te)
        g, _, _ = gini(test["Frequency"].to_numpy(), p, w_te)
        freq_pred[name] = p
        res["frequency"][name] = {"poisson_deviance": float(dev), "d2_vs_mean": float(1 - dev / null_dev), "gini": g,
                                  "predicted_claims": float((p * w_te).sum()), "observed_claims": float(test["ClaimNb"].sum())}

    # 2. severity: attritional (Gamma GLM, capped at u) + EVT excess (GPD)
    claims_tr = train[train["ClaimNb"] > 0]
    claims_te = test[test["ClaimNb"] > 0]
    sev_all = claims_tr["AvgClaim"].to_numpy()
    u = float(np.quantile(sev_all, 0.99))
    excess = sev_all[sev_all > u] - u
    gpd = fit_gpd(excess)
    p_exceed = float((sev_all > u).mean())
    large_load = p_exceed * gpd["mean_excess_model"]
    sev_model = make_pipeline(glm_features(), GammaRegressor(alpha=10.0, max_iter=1000))
    sev_model.fit(claims_tr, np.minimum(claims_tr["AvgClaim"], u), gammaregressor__sample_weight=claims_tr["ClaimNb"])
    att_te = sev_model.predict(claims_te)
    res["severity"] = {
        "threshold_u_p99": u, "claims_above_u": int((sev_all > u).sum()), "p_exceed": p_exceed, "gpd": gpd,
        "empirical_mean_excess": float(excess.mean()), "large_loss_load_per_claim": large_load,
        "attritional_gamma_deviance_test": float(mean_gamma_deviance(np.minimum(claims_te["AvgClaim"], u), att_te, sample_weight=claims_te["ClaimNb"])),
        "mean_claim_train": float(np.average(sev_all, weights=claims_tr["ClaimNb"])),
        "mean_attritional_pred_plus_load": float(np.average(att_te, weights=claims_te["ClaimNb"]) + large_load),
        "mean_claim_test_observed": float(np.average(claims_te["AvgClaim"], weights=claims_te["ClaimNb"])),
    }

    # 3. pure premium
    sev_te_all = sev_model.predict(test) + large_load
    pp = {"freq_gbm_x_sev": freq_pred["poisson_gbm"] * sev_te_all, "freq_glm_x_sev": freq_pred["poisson_glm"] * sev_te_all}
    tweedie = make_pipeline(glm_features(), TweedieRegressor(power=1.9, alpha=0.1, max_iter=10000))
    tweedie.fit(train, train["PurePremium"], tweedieregressor__sample_weight=w_tr)
    pp["tweedie_glm"] = tweedie.predict(test)
    res["pure_premium"], lorenz = {}, {}
    obs_total = float(test["ClaimAmount"].sum())
    for name, p in pp.items():
        g, cw, cl = gini(test["PurePremium"].to_numpy(), p, w_te)
        lorenz[name] = (cw, cl)
        res["pure_premium"][name] = {"gini": g, "predicted_total": float((p * w_te).sum()), "observed_total": obs_total,
                                     "predicted_over_observed": float((p * w_te).sum() / obs_total),
                                     "tweedie_deviance_p1.9": float(mean_tweedie_deviance(test["PurePremium"], np.maximum(p, 1e-9), sample_weight=w_te, power=1.9))}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    artefacts = {"df": df, "train": train, "test": test, "freq_pred": freq_pred, "pp": pp, "lorenz": lorenz,
                 "sev_all": sev_all, "u": u, "gpd": gpd, "freq_models": freq_models, "sev_model": sev_model}
    return res, artefacts
