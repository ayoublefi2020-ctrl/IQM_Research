# Emerald translation check

We ran a distance-3 Z memory on 17 physical qubits. Each of two jobs used 4,000 shots, zero SWAPs, no routing and no mid-circuit resets. The translator mapped nonempty Stim layer boundaries to Qiskit barriers that survived IQM serialization. We compared the results with the [earlier run](../../hardware/20261121T192624300601Z) on the same patch and calibration set. Both runs used identical decoder models at each length.

| Rounds | Earlier failures | With barriers | New logical failure probability (95% Wilson interval) | Mean detector firing, earlier → new |
|---:|---:|---:|---:|---:|
| 3 | 1,435 / 5,000 | 402 / 4,000 | 10.05% (9.16–11.02%) | 22.68% → 11.88% |
| 5 | 2,218 / 5,000 | 644 / 4,000 | 16.10% (14.99–17.27%) | 29.34% → 13.64% |

The two new probabilities give a fitted logical error per round of 3.68% (model-based 95% interval 3.45–3.92%). The original and modified live request builders both preserved the ideal joint distribution of the Stim measurement record. We checked native rotations, CZs, physical measurement locations, classical bit indices, and the signs and number of independent measurement parity constraints. The barriers removed cross-layer interleaving from the serialized CZ and measurement list. The two versions had identical rotation, CZ and measurement counts, with 14 added barriers at 3 rounds and 24 at 5 rounds.

The measurements support a scheduling effect. The historical comparison and absence of pulse timing measurements leave the individual physical causes unresolved. Job IDs, full serialized gate lists, layouts, decoder circuits and raw counts are in this folder. The barrier option for the normal hardware runner is `--preserve-ticks`.
