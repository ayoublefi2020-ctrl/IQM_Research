# Distance-5 experiment

The existing native memory builder works at distance 5. Geometry, stabilizer commutation, noiseless sampling, graphlike distance and selected injected X/Y/Z, double and measurement faults passed for the stated test cases. Both Qiskit and Qrisp payloads and two randomized twirl seeds were audited at 3 and 20 rounds in X and Z memory on the offline SDK fixture. See research_data/distance_5/validation.json and fixture_compilation.json.

The live Emerald graph has no exact zero-SWAP embedding for this standard 49-qubit distance-5 interaction graph. The routed Qiskit Z-memory control passed ideal stabilizer simulation and native IQM validation with 115 routing SWAPs and 585 native CZs. The 1,000-shot, three-round pilot with standard DD was submitted as 01a20157-6bba-7289-a82e-65f205f0aedb. Job state and any measurements are stored in research_data/distance_5/routed_hardware. No live Qrisp or twirled distance-5 jobs were submitted. Those configurations need validated routed payloads and a separate routing study.

The pilot uses a decoder prior for the logical native circuit with p = 0.003 and correlated matching. It does not model each routed SWAP fault. Its role is to establish feasibility and measure the observed logical result for this routed implementation.

The exact submitted IQM instructions were independently re-simulated as native Clifford gates. All 97 measurement keys and 73 independent parity constraints matched, including logical parity signs. See payload_verification.json.

The live status lookup returned **waiting**. The current worker continues polling the existing job. The dashboard reads the saved status and loads measurement statistics only after raw data and decoding outputs exist. Use dashboard/pilot_status.py to refresh the status or the pilot runner to resume retrieval.

## Completed Emerald pilot

Job 01a20157-6bba-7289-a82e-65f205f0aedb completed. Returned 1,000 shots. Correlated matching decoded 361 logical failures, 36.10% with 95% Wilson interval 33.18% to 39.12%. The circuit was Qiskit Z memory, distance 5, three rounds, twirling off, standard DD, with 115 routing SWAPs and 585 CZ gates. Raw measurements and decoded outcomes are in research_data/distance_5/routed_hardware. The archive now indexes 70 measured IQM jobs and 561,000 shots across both distances.

The first poll reached its timeout before the job completed. The runner now resumes the existing IQM job using the saved circuit and calibration metadata and checks the terminal status before accessing measurements.

## Later routing and basis experiments

The follow-up and completed primary analyses are documented in [Basis and routing tests](BASIS_AND_ROUTING_TESTS.md). The new routed job, 01a201eb-eed8-760e-aec5-ea1ea62089bd, returned 1,000 shots at the same calibration requested for the new distance-3 X/Z job.
