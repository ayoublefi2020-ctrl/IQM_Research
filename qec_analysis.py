"""Shared detector models, binomial fit and plotting for simulation and hardware."""
import numpy as np
import pymatching
from scipy.optimize import brentq, minimize_scalar
from scipy.special import xlogy


# Multipliers for gate, initial preparation/reset, readout, and per-round data noise.
PROFILES = {"uniform": (1, 1, 1, 1), "readout": (1, 1, 3, 1), "idle": (1, 1, 1, 3)}
NOISE_KEYS = ("after_clifford_depolarization", "after_reset_flip_probability",
              "before_measure_flip_probability", "before_round_data_depolarization")


def noise_model(p, profile):
    return {key: p * scale for key, scale in zip(NOISE_KEYS, PROFILES[profile])}


def matcher(circuit, decoder):
    if decoder not in ("plain", "correlated"):
        raise ValueError("Unknown decoder")
    return pymatching.Matching.from_detector_error_model(
        circuit.detector_error_model(decompose_errors=True), enable_correlations=decoder == "correlated")


def failures(model, decoder, events, observed):
    prediction = model.decode_batch(events, enable_correlations=decoder == "correlated")
    if prediction.shape != observed.shape:
        raise ValueError("Decoder and observable dimensions disagree")
    return np.any(prediction != observed, axis=1)


def wilson(k, n):
    """95% Wilson interval for independent shots, including zero failures."""
    z = 1.95996398454
    p = k/n
    center = (p + z*z/(2*n))/(1+z*z/n)
    half = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))/(1+z*z/n)
    return max(0., center-half), min(1., center+half)


def probability(r, rate):
    if rate >= .5:
        return np.full_like(r, .5, dtype=float)
    return -.5*np.expm1(r*np.log1p(-2*rate))


def fit_rate(rounds, errors, shots):
    """Challenge model, binomial maximum likelihood and approximate profile 95% CI."""
    r, k, n = map(np.asarray, (rounds, errors, shots))
    if len(set(r)) < 2:
        raise ValueError("At least two distinct round counts are required for a fit.")
    def loss(rate):
        p = probability(r, rate)
        return -sum(xlogy(k, p) + xlogy(n-k, 1-p))
    estimate = minimize_scalar(loss, bounds=(0,.5), method="bounded",
                               options={"xatol": 1e-13}).x
    estimate = min((0., estimate, .5), key=loss)
    def crossing(x):
        return loss(x) - loss(estimate) - 1.9207294
    low = brentq(crossing, 0, estimate) if crossing(0) > 0 else 0.
    high = brentq(crossing, estimate, .5) if crossing(.5) > 0 else .5
    return dict(rate=float(estimate), low=float(low), high=float(high))


def plot_curves(series, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7,4.5), layout="constrained")
    for label, (rs, ks, ns) in series.items():
        r, k, n = map(np.asarray, (rs, ks, ns))
        values = k/n
        lo, hi = np.asarray([wilson(a,b) for a,b in zip(k,n)]).T
        artist = ax.errorbar(r, values, yerr=np.maximum(0,[values-lo,hi-values]), fmt="o",
                             label=label, capsize=3)
        if len(set(r)) >= 2:
            rate = fit_rate(r,k,n)["rate"]
            x = np.linspace(min(r), max(r), 100)
            ax.plot(x, probability(x,rate), color=artist[0].get_color())
    ax.set(xlabel="Stabilizer rounds", ylabel="Decoded logical failure probability", title=title)
    ax.legend()
    fig.savefig(path,dpi=170)
    plt.close(fig)
