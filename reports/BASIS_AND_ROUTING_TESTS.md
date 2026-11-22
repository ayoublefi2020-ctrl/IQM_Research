# QuantumTN · Emerald basis and routing tests

All four rows use Qiskit, three stabilizer rounds, no ancilla reset, twirling off, standard dynamical decoupling and the same correlated matching method. The primary decoder uses the logical native circuit with the balanced prior at p = 0.003. Each row represents a separate circuit execution. Intervals are 95% Wilson intervals for independent shots conditional on that execution. They exclude calibration drift.

| Test | IQM job | Failures / shots | Logical failure probability | SWAPs | Native CZ | Rotations | Depth |
|---|---|---:|---|---:|---:|---:|---:|
| d3 X memory | 01a201e9-e787-76f5-b924-462586132ec7 | 50 / 1,000 | 5.00% [3.81%, 6.53%] | 0 | 72 | 92 | 30 |
| d3 Z memory | 01a201e9-e787-76f5-b924-462586132ec7 | 48 / 1,000 | 4.80% [3.64%, 6.31%] | 0 | 72 | 94 | 30 |
| d5 Z original | 01a20157-6bba-7289-a82e-65f205f0aedb | 361 / 1,000 | 36.10% [33.18%, 39.12%] | 115 | 585 | 932 | 201 |
| d5 Z follow-up | 01a201eb-eed8-760e-aec5-ea1ea62089bd | 363 / 1,000 | 36.30% [33.38%, 39.33%] | 78 | 474 | 723 | 204 |

The two d3 arms share one job and physical layout. The d5 follow-up requested the same calibration set as the d3 job, `7d7ebe74-3674-4b32-baa2-fa0117ecbef9`. The original d5 job used `ecec1d0a-1529-4c90-9b02-d1b30ddaa2e3`. Calibration ID identifies the IQM device settings used for compilation and execution. The job ID identifies a particular submission.

## Why the distance-5 intervals sit high

Both d5 runs had about 360 decoded failures. The interval measures uncertainty around that fraction. The new route used the lowest SWAP count among 24 tested SABRE seeds. It saved 111 CZ gates, but its native depth increased by 3. The change of 2 failures across different calibrations provides no clear evidence of better hardware performance. On the shared calibration, d3 Z had 31.5 percentage points fewer failures than d5 Z with the primary decoder. These are three-round probabilities. A per-round fit requires measurements at more round counts.

Replaying both submitted native gate streams verified the ideal measurement distribution, 97 measurement keys and 73 determined parities per circuit. Direct XORs on all 1,000 recorded shots per job reproduced all 72 Stim detector bits and the logical observable for every shot. Decoding reproduced the original counts and detector firing rates. These checks cover the submitted circuits and the local analysis. Pulse-level execution and physical fault locations cannot be verified from the saved bitstrings alone.

The original decoder omits explicit fault locations on gates inserted during routing. An alternative decoder used each submitted physical CZ and rotation, with assumed independent depolarizing probabilities of 0.003 and 0.00075 respectively, and readout flips of 0.003. On the original job this produced 371 failures (37.10%, paired exact p = 0.596). On the follow-up it produced 323 failures (32.30%, 95% CI 29.47%–35.26%). It corrected 157 previously failed shots and introduced 117 new failures (two-sided exact McNemar p = 0.018). This is a retrospective comparison using the same measurements. The observed benefit depended on the circuit and job.

## Simulated isolation of routing overhead

Each cell gives logical failures per 20,000 simulated shots, decoded with matched correlated matching. Only native CZ operations had noise. Initialization, rotations, idles and measurements were ideal. The direct logical circuit is a simulation reference. Seed 221126 was used in Stim.

| Assumed CZ depolarization | Direct, 240 CZ | Original route, 585 CZ | Follow-up route, 474 CZ |
|---|---:|---:|---:|
| 0.003 | 11 (0.055%) | 139 (0.695%) | 83 (0.415%) |
| 0.010 | 221 (1.105%) | 2,129 (10.645%) | 1,331 (6.655%) |

Routing raises the simulated failure probability at both tested noise levels. Both hardware jobs had mean detector firing near 27.5%. The simplified simulation underpredicts the observed hardware failure. These measurements alone cannot separate idle errors, readout, correlated faults, gate noise or other unmodeled effects.

## Files and offline verification

* `research_data/distance_3/basis_pilot/` contains both raw measurement arrays, the submitted instructions, Stim models, counts and job metadata.
* `research_data/distance_5/routed_hardware/` and `research_data/distance_5/routing_followup/` contain the two hardware jobs. The follow-up includes the 24 compilation candidates.
* `research_data/distance_5/pilot_audit.json` and `followup_audit.json` contain independent parity checks, alternate decodes, paired tests and simulation intervals.
* `research_data/distance_3/manifest.json` maps historical result paths to their archived copies.

From the project directory after installing the dependencies, replay the distance-5 analysis with `.\.venv\Scripts\python.exe dashboard/audit_distance5.py`. The script reads saved shots and runs simulations locally. Run `START_IQM_DASHBOARD.cmd` to explore the measurements.
