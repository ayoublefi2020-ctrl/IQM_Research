# Distance 3 versus distance 5

In the newly matched balanced-noise simulation, distance 3 and distance 5 used identical per-operation probabilities (0.003), correlated matching, the alternating schedule and 4,000 shots per point.

| Rounds | Distance 3 failures | Distance 5 failures |
|---:|---:|---:|
| 3 | 46 / 4,000 (1.15%) | 12 / 4,000 (0.30%) |
| 5 | 71 / 4,000 (1.775%) | 24 / 4,000 (0.60%) |
| 20 | 262 / 4,000 (6.55%) | 94 / 4,000 (2.35%) |

This is evidence for improved protection under the simulated noise model. The live distance-5 pilot includes routing overhead. One routed three-round data point cannot establish a matched distance-scaling factor or a per-round decay rate. The distance-3 benchmark uses a zero-SWAP native patch and a separately characterized decoder.

The matched balanced-noise fit gave 0.356% per round at distance 3 (profile 95% interval 0.321% to 0.394%) and 0.118% at distance 5 (0.099% to 0.140%). The estimated simulation suppression factor is 3.02. Binomial deviance goodness-of-fit p-values are about 0.83 for both. There are only three tested round counts and this result applies to the selected simulator noise model.

## Measured Emerald pilot

The routed distance-5 control recorded 361 logical failures in 1,000 shots after three rounds (36.10%, 95% Wilson interval 33.18%-39.12%). The earlier distance-3 benchmark recorded 508 failures in 10,000 shots (5.08%, 95% Wilson interval 4.67%-5.53%). The pilot had 115 SWAPs and 585 CZs, and used a different decoder. The higher observed failure rate applies to that routed implementation. The experiment did not isolate code distance, routing or decoder effects.
