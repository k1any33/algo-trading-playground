import numpy as np
import pandas as pd


def fisher_transform(high: pd.Series, low: pd.Series, period: int = 10) -> pd.Series:
    """Ehlers Fisher Transform.

    Uses recursive smoothing: val[i] = 0.33 * raw[i] + 0.67 * val[i-1]
    then Fisher[i] = 0.5 * ln((1+val)/(1-val)) + 0.5 * Fisher[i-1]
    """
    mid = (high + low) / 2
    hi_n = mid.rolling(period).max()
    lo_n = mid.rolling(period).min()
    rng = (hi_n - lo_n).replace(0, np.nan)
    raw = 2 * ((mid - lo_n) / rng - 0.5)

    val  = np.zeros(len(mid))
    fish = np.zeros(len(mid))
    raw_arr = raw.fillna(0).to_numpy()

    for i in range(1, len(mid)):
        val[i] = 0.33 * raw_arr[i] + 0.67 * val[i - 1]
        val[i] = max(min(val[i], 0.999), -0.999)
        fish[i] = 0.5 * np.log((1 + val[i]) / (1 - val[i])) + 0.5 * fish[i - 1]

    out = pd.Series(fish, index=mid.index, name="fisher")
    out.iloc[:period] = np.nan
    return out


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()
