# QuantumTN competition summary

QuantumTN implements no-reset rotated surface-code memories with shared Stim measurement semantics, Qiskit and Qrisp compilation, hardware-aware placement, gate twirling and offline decoding. The dashboard connects the preserved distance-3 results to filters, point provenance, searchable records, exports and calibrated topology. It also includes distance-5 geometry and simulated noise controls.

The controlled 10,000-shot three-round Qrisp result with gate twirling and characterized readout weights was 508 logical failures (5.08%). The Qrisp control and twirled circuits were run at 3 and 5 rounds. Characterized readout changes decoder weights on the same measured records.

The current live Emerald CZ graph has no exact zero-SWAP embedding of the full distance-5 interaction graph. A separate routed Qiskit pilot evaluates the cost of running with routing overhead. Its status is recorded in the distance-5 experiment report.
