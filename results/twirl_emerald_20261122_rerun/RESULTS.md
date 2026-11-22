# Emerald rerun with colleague-style SI1000 priors

Four independent campaigns ran on IQM Emerald with the four supplied credentials. The second and third credentials were the same string; they were used for two separate runs. Each campaign submitted Qiskit and Qrisp control and gate-twirled circuits at rounds 1-5. Each pipeline and round used 20 randomized twirling variants and 20 interleaved controls of 200 shots. There were 40 distinct hardware jobs and 320,000 shots. All jobs used calibration `ecec1d0a-1529-4c90-9b02-d1b30ddaa2e3`.

Fixed settings were distance 3, Z memory, 17 physical qubits on the colleague's patch, no mid-circuit reset, zero SWAPs, standard dynamical decoupling and BP+OSD decoding. The prior used the colleague NoiseModel.si1000(0.01) channel strengths and placement rules adapted to this circuit. The model sets decoder weights; all shots came from physical hardware. Rounds 3 and 5 match the colleague's earlier matched comparison. The additional rounds extend the twirling sweep.

Each cell below is failures out of 16,000 shots pooled across the four campaigns, followed by the percentage.

| Rounds | Qiskit control | Qiskit twirled | Qrisp control | Qrisp twirled |
|---:|---:|---:|---:|---:|
| 1 | 162 (1.013%) | 172 (1.075%) | 161 (1.006%) | 175 (1.094%) |
| 2 | 636 (3.975%) | 659 (4.119%) | 653 (4.081%) | 583 (3.644%) |
| 3 | 963 (6.019%) | 1003 (6.269%) | 977 (6.106%) | **886 (5.538%)** |
| 4 | 1295 (8.094%) | 1379 (8.619%) | 1407 (8.794%) | 1347 (8.419%) |
| 5 | **1748 (10.925%)** | 1764 (11.025%) | 1778 (11.113%) | 1814 (11.338%) |

At three rounds Qrisp twirled had 91 fewer failures than Qrisp control, a 0.569 percentage-point reduction. The 95% paired block-bootstrap interval was 0.063 to 1.063 points. Compared with Qiskit control, Qrisp twirled had 77 fewer failures, a 0.481-point difference. Its bootstrap interval was -0.006 to 0.969 points, so that cross-pipeline ranking is marginal. At five rounds Qiskit control had the lowest observed error. The gaps between all four new settings at five rounds were small relative to block uncertainty.

Fitted logical error per round across 1-5 rounds was 2.117% for Qiskit control, 2.198% for Qiskit twirled, 2.197% for Qrisp control and 2.117% for Qrisp twirled. The Qiskit control and Qrisp twirled fits were effectively tied. The simple constant-rate fit compresses a curve with visible round dependence, so the measured round-specific rates are the primary comparison.

The colleague's earlier matched experiment reported BP+OSD failures of 325/4,000 (8.125%) at three rounds and 520/4,000 (13.000%) at five rounds. The new Qrisp twirled aggregate was 5.538% at three rounds, 2.588 points lower. New Qiskit control was 10.925% at five rounds, 2.075 points lower. The colleague data came from a separate job on an earlier date. Equal calibration IDs and decoder settings do not remove time drift or other between-job variation, so these are descriptive differences.

The two pipelines used the same native PRX, CZ and measurement counts at each round length. Twirling preserved those counts and passed the ideal parity audits. The complete per-campaign counts, job IDs, raw measurements, audit files and decoder results are in the subfolders. The new curves are in `logical-error-curves.png`.
