# Two distance-3 circuits on Emerald

Both projects ran in IQM job `01a1ffb6-b7c7-7681-936e-4fa17599a7da`. Each stored one logical Z bit on the colleague's 17-qubit patch with no resets between rounds, zero SWAPs and standard dynamical decoupling. Each received 4,000 shots at 3 rounds and 4,000 at 5 rounds. All four circuits used calibration `ecec1d0a-1529-4c90-9b02-d1b30ddaa2e3`. Reflecting the horizontal code coordinate aligned the two patches, including the logical Z readout row. Both ideal native instruction streams passed the measurement parity checks.

| Circuit and decoding method | Failures at 3 rounds | Failures at 5 rounds | Effective fitted error per round |
|---|---:|---:|---:|
| Ours, common BP+OSD with SI1000 | 236 (5.900%) | 456 (11.400%) | 2.332% |
| Colleague, common BP+OSD with SI1000 | 325 (8.125%) | 520 (13.000%) | 2.901% |
| Ours, local likelihood with device priors | 232 (5.800%) | 462 (11.550%) | 2.339% |
| Colleague, BP+OSD with characterized readout and SI1000 | 310 (7.750%) | 491 (12.275%) | 2.735% |

With common decoding, the failure probability difference in our favor was 2.225 percentage points at 3 rounds and 1.600 at 5. Approximate independent-shot 95% intervals were 1.11–3.34 and 0.17–3.03 points. With project-specific decoding the estimated advantages were 1.950 and 0.725 points, with intervals 0.85–3.05 and −0.69–2.14. These intervals reflect shot noise within this job. Between-job variation would require repetition. The two-point constant-rate fit for our circuit with common decoding showed a departure from the assumed model (Pearson p = 0.011), so the measured probabilities are the primary outcomes.

The two circuits used 72 CZ gates at 3 rounds and 120 at 5. Our design used 94 and 150 single-qubit rotations versus 104 and 172 in the colleague's design. The designs also differ in CZ layer order and barrier placement. The experiment measures their combined effect and cannot assign causality to one change.

Independent replay of the colleague's earlier standard-DD Z run with BP+OSD and SI1000 gave 115, 219, 311, 387 and 452 failures at lengths 1 through 5, out of 4,000 shots each, reproducing the reported 2.654% fitted rate.

[Run settings and circuit audits](settings.json) · [Common decoder scores](scores.json) · [Project-specific scores](project-decoders.json) · [Job ID](job.json) · [Reproduction script](../../../compare_peer.py)
