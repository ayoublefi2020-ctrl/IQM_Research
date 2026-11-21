# Running the Emerald surface-code experiment

This document covers the earlier CX-based benchmark. The [current native-CZ study and runner guide](OPTIMIZATION.md) lists the selected settings and independent validation results. The original script raw_stim_d3_surface_code.py provides the with-reset reference.

## Reproduce the local runs

```powershell
python verify_qec.py -v
python simulate_qec.py
python simulate_qec.py --distances 3 --bases Z --profiles uniform --p 0.003 --rounds 2 3 5 8 --shots 100000 --repeats 2 --seed 625315 --output results/emerald_candidate
```

The first sweep takes 4,000 shots per repeat, two repeats per condition, in each of two independent phases. It covers distances 3 and 5, X and Z memories, 2, 3, 5 and 8 rounds, four noise strengths (0.001, 0.003, 0.005 and 0.01), and three noise profiles. The uniform profile applies p to post-Clifford depolarization, preparation faults, readout flips, and per-round data depolarization. The readout profile triples only readout flips. The idle profile triples only per-round data depolarization. Preparation faults are applied after actual preparations. No inter-round reset is performed. A readout flip affects only the recorded classical bit. This model omits state-dependent relaxation, leakage, crosstalk, drift and noise from the extra native gates used to compile a CX.

Each decoder sees exactly the same shots within a condition. Each selection and validation repeat uses an independent seed. The program selects the single decoder with the fewest selection failures summed across the requested settings, breaking ties in favor of plain matching. It reports paired differences on fresh validation shots. The broad sweep weights conditions equally. The focused sweep determines the default for the planned distance-3 Z hardware sweep. Both decoders remain available for replaying hardware counts.

Each output directory contains selection and validation CSVs (seeds, conditions, shots, paired errors), selection.json, validation_fits.csv, and validation.png. The plot illustrates one slice; the CSV covers every setting. The seed, library version, machine instruction set and the shots per sampling call can all affect exact reproducibility.

## Results

Of 1,536,000 validation shots in the broad sweep, plain matching failed on 65,604 and two-pass correlated matching on 59,811. Correlated matching improved the aggregate by 8.83% relative. On the focused sweep (800,000 validation shots), plain matching failed on 8,298 and correlated matching on 8,726. The held-out paired exact test gives p = 4.83e-9 for equal discordant-shot probabilities in this pooled comparison. The fixed hardware default is plain matching. Correlated matching performed better at two rounds in the focused run.

| Rounds | Shots | Plain failures | Correlated failures | Plain failure probability |
|---:|---:|---:|---:|---:|
| 2 | 200,000 | 985 | 936 | 0.4925% |
| 3 | 200,000 | 1,379 | 1,442 | 0.6895% |
| 5 | 200,000 | 2,342 | 2,467 | 1.1710% |
| 8 | 200,000 | 3,592 | 3,881 | 1.7960% |

Under the challenge model P(r) = [1 - (1 - 2e)^r]/2, the focused plain decoder fit gives e = 0.2330% per round (approximate 95% profile-likelihood interval 0.2280% to 0.2381%). The correlated fit is 0.2452% (0.2400% to 0.2504%). These intervals quantify sampling error conditional on the fit and simulator noise model. For the plain fit the Pearson goodness-of-fit statistic was 5.49 on 3 degrees of freedom. Inspect individual points and early-round behavior when applying this model to hardware.

## Compile and submit to Emerald

```powershell
python run_on_hardware.py
python -m pip install "iqm-client[qiskit]==35.0.3"
python run_on_hardware.py --live-compile
python run_on_hardware.py --submit --basis Z --distance 3 --rounds 2 3 5 8 --shots 5000
```

The first command compiles against the README's example 5 by 5 patch locally. The adapter is required only for the last two commands. Those commands read IQM_TOKEN or prompt privately. Live compilation reads the current CZ connectivity, finds an exact embedding, and disables SWAP routing. A missing embedding or incompatible target raises an error before that circuit is submitted. The offline example is sized for distance 3. Distance 5 simulation works locally; feasibility on Emerald depends on the current native graph and available qubits.

The submit command runs four jobs and requests 20,000 shots in total. Each timestamped results/hardware directory holds settings and compilation statistics. A submission also saves each job ID, the raw counts, failure counts with Wilson intervals, and per-detector firing rates. Multiple round counts produce a fitted rate and plot. Use --decoder correlated to compare another decoder, or --selection path/to/selection.json to load a different simulation selection. Hardware --p and --profile set the decoder's assumed weights. Physical noise is determined by the processor.

To re-decode an existing job locally, use its settings for distance, basis, rounds, p and profile. Example for a three-round job:

```python
import json
from pathlib import Path
from run_on_hardware import process_counts, decode_hardware_results
from surface_code import make_stim_circuit
from qec_analysis import noise_model

counts = json.loads(Path("results/hardware/YOUR_RUN/counts-r3.json").read_text())["counts"]
c = make_stim_circuit(3, 3, "Z")
syn = process_counts(counts, c, sum(counts.values()))
model = make_stim_circuit(3, 3, "Z", noise=noise_model(.003, "uniform"))
for decoder in ("plain", "correlated"):
    print(decoder, decode_hardware_results(syn, model, decoder))
```

## Circuit and placement checks

The generator replaces each ancilla measure-and-reset with a measurement. Every reference to a fresh ancilla syndrome becomes the XOR of the current raw measurement and its predecessor on that ancilla (just the current measurement on first use). Rewriting all detector parities also handles the final data boundary. X-basis preparation and readout become Hadamard rotations in Qiskit. Both runners use the same detector record.

For distance 3 and three rounds, the circuit uses 17 physical qubits, has 24 interacting pairs, and requires 72 entangling operations. On the example grid, assigning dense circuit indices to the same sites sorted by hardware index needed 216 CZs and depth 199 with SABRE routing, optimization level 1 and seed 19 in our local comparison. The geometric embedding took 72 CZs and depth 45, with routing disabled. The sorted placement is a simple baseline. These are compilation counts for the offline basis, not measured gate fidelities.

The regression suite checks noiseless detector and observable parities, graphlike distances 3 and 5, first/interior/final rounds, an alternate backend's connectivity, both compiled bases in Aer, Qiskit bit order, and the different outcomes of correctable single faults and logical strings. The real IQM target and a real job require live verification.

## How the three papers shaped the experiment

- The 2021 cyclic error-correction experiment varies the number of rounds and fits logical fidelity. Its large suppression result is for repetition codes, which protect one error type in each experiment. We adopt its round sweep and probability model. Its correlation and error-budget analysis motivates stressing readout and data noise separately. [Google Quantum AI, 2021, Figs. 2–4](https://doi.org/10.1038/s41586-021-03588-y)
- The 2023 surface-code experiment compares distance 5 with several distance-3 patches and tests X and Z memories. Fig. 3 starts fitting at cycle 3 to reduce boundary effects. Our sweep keeps distances and bases separate, records per-round counts, and uses the challenge's specified one-parameter fit. The paper's variation between patches is a reason to remeasure performance on Emerald. [Google Quantum AI, 2023, Figs. 2–4](https://arxiv.org/abs/2207.06431)
- The Willow study compares decoders and measures how logical performance changes with physical errors. It also isolates the effect of active leakage removal and finds rare correlated events. We can test correlated matching in software using the same samples. The processor-level leakage operations and rare-event rates in that paper require separate hardware characterization. [Google Quantum AI, Figs. 1–3](https://doi.org/10.1038/s41586-024-08449-y)

The two-pass algorithm uses PyMatching's correlation-enabled model construction and decoding. The hardware client follows IQM's provider, transpilation, submission and counts interface. [PyMatching implementation and examples](https://github.com/oscarhiggott/PyMatching) · [IQM Qiskit user guide](https://docs.iqm.tech/iqm-client/user_guide_qiskit.html)
