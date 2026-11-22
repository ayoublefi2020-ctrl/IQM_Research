# Distance-3 archive

The manifest maps each original path to its read-only-by-convention archive copy and SHA-256 checksum. The snapshot includes supporting comparisons, simulations and compilation artifacts. Use source and execution metadata to identify measurements. Original files remain at their original locations.

## Inventory

- 565 verified source copies with checksums.
- 69 unique distance-3 IQM jobs and 560,000 physical shots in the normalized index.
- IQM job IDs, per-result source paths, recovered metadata and snapshot package versions are listed in metadata/snapshot.json.
- Runs include the original hardware series, translation checks, matched project comparison, twirling experiments and friend-model confirmation. Some raw files are grouped bitstring counts. These recover measured bitstrings but cannot reconstruct their acquisition order. NPZ archives preserve saved block and shot order.
- Detector events and observables are reconstructed only where the saved raw measurements and compatible Stim decoder circuit are available. BP+OSD per-shot predictions, exact historical runtime package versions, and full historical calibration fidelities were not recorded for every job.
- No known additional job was downloaded during this snapshot. The counts cover jobs linked to local saved records, and the metadata distinguishes copied files from normalized result rows.
