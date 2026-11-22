# Comparison of three Emerald surface-code projects

Friend 2 source: https://github.com/amine20011111/testhackathon at commit 2c58d88b884a8bb80c9f3bdd3397038f968001ac. Friend 3 source: https://github.com/AhmedAmineLoukil/PushQuantum_2026 at commit 1599a53a099e1603236ff17633516eaf43d2eb63.

The common design ideas are a distance-3, 17-qubit, no-reset Z-memory circuit on a pinned zero-SWAP patch, standard server dynamical decoupling, and BP+OSD decoding. Friend 3's measured-readout characterization was tried as an alternative decoder prior. This project's twirling uses IQM gate-frame tracking and preserves the original PRX and CZ counts. Friend 2's CX Pauli wrapping and friend 3's CZ Pauli wrapping change circuit execution and were reviewed as alternatives. Friend 3 reports that its added-gate twirl hurt on Emerald; this project kept the gate-count-preserving implementation.

The new hardware experiment used the same 17 physical qubits, calibration ecec1d0a-1529-4c90-9b02-d1b30ddaa2e3, zero SWAPs, standard DD, and SI1000 p = 0.01 for all four settings. Qiskit and Qrisp each ran twirled and control circuits at 3 and 5 rounds. Each setting received 2,000 pilot shots and 10,000 independent confirmation shots, spread across 20 interleaved randomized variants or controls. Eight hardware jobs supplied 96,000 shots in total. Every compiled circuit passed the ideal parity audit and preserved 24 CZs per round.

| Round | Shots per setting | Qiskit control | Qiskit twirled | Qrisp control | Qrisp twirled |
|---:|---:|---:|---:|---:|---:|
| 3 | 2,000 | 116 (5.80%) | 123 (6.15%) | 153 (7.65%) | 122 (6.10%) |
| 5 | 2,000 | 235 (11.75%) | 237 (11.85%) | 204 (10.20%) | 212 (10.60%) |
| 3 | 10,000 | 601 (6.01%) | 571 (5.71%) | 576 (5.76%) | **535 (5.35%)** |
| 5 | 10,000 | 1007 (10.07%) | 1032 (10.32%) | **999 (9.99%)** | 1034 (10.34%) |

The pilot's top circuit at 3 rounds was Qiskit control; the confirmation's was Qrisp twirled. At 5 rounds Qrisp control led in both stages under the fixed decoder. The small margins require caution. This test contains only rounds 3 and 5, so a fitted per-round logical error would be less robust than the earlier five-round sweep.

## Decoder-prior comparison on identical hardware shots

The pilot also compared SI1000 p = 0.005, 0.01 and 0.02 with friend 3's measured-readout characterization added to SI1000 p = 0.01. The confirmation checked the fixed p = 0.01 prior and the characterized option. The characterization was recorded earlier and may have drifted.

| Confirmation setting | Fixed SI1000 p = 0.01 | Characterized readout + SI1000 |
|---|---:|---:|
| Qiskit control, 3 rounds | 601 (6.01%) | 569 (5.69%) |
| Qiskit twirled, 3 rounds | 571 (5.71%) | 554 (5.54%) |
| Qrisp control, 3 rounds | 576 (5.76%) | 561 (5.61%) |
| **Qrisp twirled, 3 rounds** | **535 (5.35%)** | **508 (5.08%)** |
| Qiskit control, 5 rounds | 1007 (10.07%) | **988 (9.88%)** |
| Qiskit twirled, 5 rounds | 1032 (10.32%) | 1013 (10.13%) |
| Qrisp control, 5 rounds | 999 (9.99%) | 993 (9.93%) |
| Qrisp twirled, 5 rounds | 1034 (10.34%) | 995 (9.95%) |

The characterized decoder reduced failures in every confirmed cell on the same physical shots. At 3 rounds the observed best is Qrisp twirled with characterized readout, 508/10,000. At 5 rounds Qiskit control with characterized readout is lowest at 988/10,000. The prior is a decoder change applied after hardware execution, not a physical noise reduction or a new hardware circuit.

## Previously reported results

Friend 2 reports a fitted Z-memory LER of 2.56% per round using its Qrisp circuit with standard DD and BP+OSD over rounds 1-5. Friend 3 reports 2.61% per round using its Qiskit circuit over rounds 1, 2, 3, 4, 6 and 8. This project's previous five-round matched sweep gave 2.117% for Qiskit control and Qrisp twirled, with poor constant-rate fit. Those per-round estimates come from different round sets, hardware jobs, circuit schedules and sometimes different patches. They are descriptive historical numbers; the round-specific failure rates above are the controlled comparison from the new jobs. Neither friend's circuit was submitted in these eight jobs.

The complete job IDs, raw measurements, per-block decoding errors, compilation audits, and settings are saved under the pilot_2000 and confirm_10000 folders. The comparison.json file holds all counts and decoder-prior results. The hardware-comparison.png figure shows both shot stages.
`nThe 95% Wilson intervals for the two leading characterized three-round results overlap: Qrisp twirled 4.67%-5.53%, Qiskit twirled 5.11%-6.01%. The 0.46 percentage-point ranking should be treated as observed performance in this confirmation run, not a proven persistent advantage.
