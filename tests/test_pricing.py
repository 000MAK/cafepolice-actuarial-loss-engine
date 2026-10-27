import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pricing import clean, fit_gpd, gini  # noqa: E402


class PricingTests(unittest.TestCase):
    def test_gini_perfect_random_and_reversed(self):
        y = np.array([0, 0, 0, 1, 2, 5.0])
        w = np.ones_like(y)
        perfect, _, _ = gini(y, y, w)
        reversed_, _, _ = gini(y, -y, w)
        self.assertGreater(perfect, 0.5)
        self.assertAlmostEqual(reversed_, -perfect, places=9)

    def test_clean_rules(self):
        df = pd.DataFrame({"ClaimNb": [0, 1, 6, 2], "Exposure": [1.5, 0.5, 1.0, 1.0], "ClaimAmount": [0.0, 0.0, 600.0, 400.0]})
        out, report = clean(df)
        self.assertEqual(report["exposure_capped"], 1)
        self.assertEqual(report["claims_without_amount"], 1)
        self.assertEqual(out["Exposure"].max(), 1.0)
        self.assertEqual(out["ClaimNb"].tolist(), [0, 0, 4, 2])          # missing amount -> claim-free; cap at 4
        self.assertEqual(out["AvgClaim"].tolist(), [0.0, 0.0, 150.0, 200.0])

    def test_gpd_recovers_shape(self):
        x = stats.genpareto.rvs(0.4, scale=1000, size=20000, random_state=1)
        fit = fit_gpd(x)
        self.assertAlmostEqual(fit["xi"], 0.4, delta=0.05)
        self.assertAlmostEqual(fit["mean_excess_model"], 1000 / 0.6, delta=150)


if __name__ == "__main__":
    unittest.main()
