Checkpoint 1. Archive snapshot created and source/copy SHA-256 verified. Recheck with .venv\Scripts\python.exe dashboard/archive.py.
Checkpoint 2. Normalized 166 result rows, 69 unique IQM jobs and 560,000 nonduplicate hardware shots. Dashboard shell created.
Checkpoint 2. Local dashboard and Edge smoke passed archived shot view, missing-data state, 49-node explorer, X-memory simulation, keyboard presentation and CSV.
Checkpoint 3. Existing verify_qec.py and 12 focused distance/basis/round validation cases passed. 24 matched Stim runs saved at 3, 5 and 20 rounds across four noise profiles.
Checkpoint 4. Live CZ topology saved. Distance 3 exact placement verified. Distance 5 exact placement unavailable in this calibration. Both pipelines and twirl seeds passed the offline fixture checks through 20 rounds.
Checkpoint 5. Routed d=5, Z, 3 rounds, Qiskit control pilot job 01a20157-6bba-7289-a82e-65f205f0aedb. Saved compilation and job ID under research_data/distance_5/routed_hardware. Resume with .venv\Scripts\python.exe dashboard/distance5_pilot.py --submit (reconnects to that job).
Checkpoint 6. Database and dashboard read measured, simulated and topology data locally. Rebuild with $env:PYTHONPATH='.' followed by .venv\Scripts\python.exe dashboard/import_data.py.
Checkpoint 7. Interactive projected 3D geometry, stabilizer and Pauli demo, actual connectivity and shot heatmap available. Browser smoke uses node dashboard/browser_smoke.cjs.
Checkpoint 8. Six-scene keyboard presentation and demo reports available. Launch with START_IQM_DASHBOARD.cmd.

Verified all known distance-3 job files link to indexed local raw measurement files. The Windows CMD launcher opened the site. Edge smoke includes the raw archive download, injected-error education, and the distance comparison slide. Four archive/geometry tests passed. Distance-5 Qrisp CLI compiled for X memory at 3 and 20 rounds with two twirl variants each on the SDK fixture. Exact live payload verification passed for the routed d=5 job. IQM reports waiting; no new job ID is needed.

| Area | Delivery | Verification | Outstanding |
|---|---|---|---|
| Distance-3 archive | 565 source snapshots, 69 distinct jobs, 560,000 shots | SHA-256, raw-array shapes, bitstring counts and unique normalized execution partitions | Some original acquisition order and historical package/calibration fields unavailable |
| Distance-5 science | Both bases and distances, 3/5/20 rounds, four noise profiles | Noiseless, graphlike distance, selected faults, X/Z commutation; Qiskit/Qrisp fixture payloads with and without twirling | Correlated physical faults beyond supported Pauli noise not characterized |
| Live Emerald topology | Measured CZ graph and diagrams | Exhaustive exact-subgraph search; 17-qubit distance-3 native placement | No exact distance-5 placement with this live calibration; unavailable calibration fields left blank |
| Distance-5 hardware | Routed Qiskit 1,000-shot pilot, 3 rounds, Z, untwirled | 115 routing SWAPs, 585 native CZ gates, 97 measurement keys and 73 independent parities verified | IQM status waiting. Live Qrisp and twirled d=5 not commissioned |
| Website | Local controls, archives, charts, noise lab, projected 3D, detector view, downloads, presentation | Windows CMD, Edge smoke and four Python checks | Full physical 3D layout mapping, pulse timing, decoder-prediction replay for BP+OSD, and live distance-scaling conclusion pending |

## Completed Emerald pilot

Job 01a20157-6bba-7289-a82e-65f205f0aedb completed. Returned 1,000 shots. Correlated matching decoded 361 logical failures, 36.10% with 95% Wilson interval 33.18% to 39.12%. The circuit was Qiskit Z memory, distance 5, three rounds, twirling off, standard DD, with 115 routing SWAPs and 585 CZ gates. Raw measurements and decoded outcomes are in research_data/distance_5/routed_hardware. The archive now indexes 70 measured IQM jobs and 561,000 shots across both distances.

The first poll reached its timeout before the job completed. The runner now resumes the existing IQM job using the saved circuit and calibration metadata and checks the terminal status before accessing measurements.

## November 22 · X/Z and routing follow-up

Two new Emerald jobs returned 3,000 shots in total. Distance 3 X and Z shared one job and produced 50 and 48 failures respectively. A distance-5 follow-up on that calibration reduced SWAPs to 78 and CZ gates to 474. The primary decoder produced 363/1,000 failures. Offline routing-aware re-decoding gave 323/1,000 on the same shots. The combined hardware database contains 72 unique jobs and 564,000 shots.

See reports/BASIS_AND_ROUTING_TESTS.md, research_data/distance_3/basis_pilot, research_data/distance_5/routing_followup and both audit JSON files. Reproduce the analysis with .venv\Scripts\python.exe dashboard/audit_distance5.py. The dashboard opens with a selectable workflow diagram and rotatable 3D workflow. Select X memory in the three-round hardware view to see the new test. Fourteen older Qiskit records with unknown twirling remain searchable in the archive and are excluded from the main comparison chart.

## Website walkthrough
Removed the slide deck. The local site opens on a rotatable transmon schematic and the memory experiment motivation. Characterization and twirling appear in the eight-stage framework. The distance comparison and hardware map explain their units, colors and routing implications. The hardware recommendation is inline. Edge smoke passed. At a 1440-pixel viewport the workflow graphic measured 466 pixels tall. At 390 pixels the document fit the viewport. Launch with START_IQM_DASHBOARD.cmd.
