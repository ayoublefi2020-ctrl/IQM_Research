# Hardware characterization

The saved live CZ graph originates from Emerald calibration ecec1d0a-1529-4c90-9b02-d1b30ddaa2e3. Graph coordinates in the dashboard are schematic and generated from real connectivity. Readout, T1/T2 and gate durations are unavailable in this snapshot.

Exhaustive subgraph monomorphism search found a distance-3 exact embedding and no distance-5 exact embedding. Distance 3 needs 24 distinct couplings and distance 5 needs 80. The SDK offline fixture has a different connectivity graph and admits distance 5.

For three rounds the routed distance-5 pilot contains 115 routing SWAPs before native decomposition. The native circuit has 585 CZs, 932 rotations, 97 measurements and depth 201, compared with the live zero-SWAP distance-3 placement's 72 CZs and depth 30. Each routed SWAP accounts for three additional CZs. Native instructions and the initial mapping are saved under research_data/distance_5/routed_hardware.
