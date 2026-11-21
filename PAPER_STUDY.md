# Evidence used in the no-reset memory study

All three PDFs supplied with the challenge are experimental papers by Google Quantum AI. They use different processors and error-correction protocols. We tested ideas from each paper on the Emerald challenge circuit and treated each physical noise rate as a simulation assumption.

| Local paper | Experimental evidence | What we tested and where the analogy ends |
|---|---|---|
| [Exponential suppression of bit or phase errors with cyclic error correction](s41586-021-03588-y.pdf), Figs. 2–4 | Repeated parity measurements in repetition codes exposed spatial, temporal and unexpected detector correlations. Failure versus round count gave a logical error per cycle. Their largest suppression occurred in repetition codes. | We ran memories to 50 rounds, calculated per-round fits from failures and shots, and tested whether measured detector correlations could identify injected faults. The challenge measures both stabilizer types on a rotated surface code. |
| [Suppressing quantum errors by scaling a surface code logical qubit](s41586-022-05434-1.pdf), Figs. 2–4 | The distance-5 patch modestly outperformed the distance-3 average; individual patches varied. Fig. 3 fits logical fidelity starting at cycle 3 because early cycles behave differently. Different decoders gave different rates. The hardware runs use CZ layers, local rotations, measurements and resets. | We varied distance, basis, gate order, and decoder. We report measured probabilities, a fit using all rounds and a sensitivity fit excluding round 2. Actual noisy operations are counted after converting CX gates to CZ and local rotations. The no-reset circuit and alternate layer ordering here are our design choices. |
| [Quantum error correction below the surface code threshold](s41586-024-08449-y.pdf), Figs. 1–4 | Distance 3, 5 and 7 scaling improved on Willow. The authors compared decoders, injected errors, and varied leakage removal. Rare correlated events limited a separate repetition-code experiment. Detection probability alone did not determine logical performance. | We tested distances 3, 5 and 7 in simulation, stressed readout and idle channels, and compared independent versus correlated faults with matched marginals. Our injected Pauli pairs model a specific correlated error channel. They do not reproduce multilevel leakage, cosmic radiation, or Willow's logical error floor. |

## Other primary sources

- Higgott et al. investigate how correlations change circuit-level decoding and compare belief matching with approximate maximum-likelihood decoding. This motivated evaluating both ordinary and two-pass correlated matching. [Phys. Rev. X 13, 031007](https://doi.org/10.1103/PhysRevX.13.031007), [PyMatching implementation](https://github.com/oscarhiggott/PyMatching).
- Bravyi, Suchara and Vargo explain maximum-likelihood decoding by comparing probabilities of logical classes. Their exact algorithm has different noise assumptions. Here the additional decoder sums one- and two-mechanism explanations from the undivided detector error model, splits well-separated groups in time, and falls back to matching for the remainder. This is an approximate decoder, not an implementation of their tensor-network method. [Phys. Rev. A 90, 032326](https://doi.org/10.1103/PhysRevA.90.032326).
- The IQM Qiskit adapter supports compiled circuits, device calibration and result retrieval. The layout search uses live CZ and readout metrics when available and compares exact embeddings. The local IQM fixture has synthetic metrics. [IQM user guide](https://docs.iqm.tech/iqm-client/user_guide_qiskit.html), [pinned IQM client](https://pypi.org/project/iqm-client/35.0.3/).

## Controlled correlation experiment

Run `python stress_correlations.py` to reproduce [the 120 settings](results/correlated_stress/conditions.csv). This is a separate test on the earlier Stim CX model. At the beginning of each round we inject faults on two data-qubit bonds, using either a joint XX/ZZ event or independent X/Z events with identical single-qubit marginal probabilities. A clean control receives neither. Two rates (0.002 and 0.008), two distances (3 and 5), both bases, two background strengths (0.001 and 0.005) and three lengths (3, 12 and 25 rounds) probe when the distinction matters.

For each setting we estimated local detector parity moments from 10,000 calibration shots, using no logical-outcome labels. We fit candidate channel families and rates by moment agreement. The grid of candidate rates excludes the injected nonzero rates. We evaluated the resulting ordinary matching decoder on 16,000 fresh shots per setting. Base noise and candidate fault locations were supplied to the inference procedure.

| Held-out fault family | Shots | Fit allowing only independent/nominal noise: failures | Fit also allowing joint faults: failures |
|---|---:|---:|---:|
| Nominal | 384,000 | 12,152 | 12,149 |
| Independent extra faults | 768,000 | 28,987 | 29,043 |
| Joint extra faults | 768,000 | 45,829 | 45,183 |

The more flexible model recognized the correct family in 115/120 settings. It reduced failures when joint faults existed and increased them slightly under independent faults. The hardware runner uses available IQM rotation, CZ and readout metrics and fills missing information from the selected noise profile. Learning a device-specific model of joint faults requires additional detector calibration shots. [Paired counts and test results](results/correlated_stress/summary.json)
