# IQM Emerald gate-twirling comparison

The distance-3 no-reset Z memory used the same 17-qubit patch, rounds 1 through 5, zero SWAPs, standard dynamical decoupling, and a BP+OSD decoder with SI1000 prior p = 0.01 in both pipelines. The prior is a decoder setting. The hardware supplied the noise. Each row contains 4,000 shots per column. Each pipeline and round length shared one hardware job between its two settings, for 10 jobs and 80,000 shots total.

| Rounds | Qiskit control failures | Qiskit twirled | Qrisp control failures | Qrisp twirled |
|---:|---:|---:|---:|---:|
| 1 | 48 | 24 | 43 | 38 |
| 2 | 153 | 137 | 129 | 127 |
| 3 | 223 | 251 | 228 | 208 |
| 4 | 310 | 329 | 310 | 306 |
| 5 | 427 | 375 | 398 | 375 |

Qrisp with twirling had the lowest fitted logical error per round at 1.8445%. Qrisp control gave 1.9441%. Qiskit with twirling gave 1.9589% and its control gave 2.0423%. The two twirled circuits tied at five rounds. Only Qrisp showed fewer failures with twirling at all five lengths.

For each length we interleaved 20 distinct gate-twirled variants with 20 matching control blocks of 200 shots each, alternating which ran first. The repeat-measurement adaptation uses IQM tracking and gate processing primitives, preserves measurement bits at every round and applies no readout twirling. All variants passed ideal parity and gate checks. Qrisp and Qiskit each compiled the project's memory circuit and used the same submission and decoding procedures.

The fit assumes P_L(r) = [1 - (1 - 2e)^r] / 2. A paired bootstrap resampled the 20 block pairs separately within each length, then refit both arms 10,000 times. The estimated reductions in e were 0.083 percentage points for Qiskit (95% interval -0.110 to +0.267) and 0.100 for Qrisp (-0.074 to +0.267). Both intervals include zero. In all four arms the constant-rate curve fits poorly by a shot-binomial Pearson check (4 degrees of freedom, p < 0.001). Use direct counts when comparing a specific round length. This sweep covers one calibration and the pipelines ran in separate jobs.

Each pipeline folder includes the settings, IQM job IDs, compressed measurement records, compilation audits, per-block decoder failure counts and fit. The comparison.json file includes the paired intervals. The runner is twirl_memory.py at the repository root.
