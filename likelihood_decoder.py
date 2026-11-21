"""Low-order marginal likelihood on Stim's undecomposed detector error model.

For a nonzero syndrome s pick a fired detector. Exactly one member of
any pair with XOR signature s must touch that detector. This finds every
one- and two-mechanism explanation without materializing a quadratic table.
For a syndrome with no such explanation, use ordinary matching.
"""
from collections import defaultdict
from functools import lru_cache

import numpy as np
import pymatching


class FaultLikelihoodDecoder:
    """Low-weight DEM decoder for a single binary logical observable.

    Independent mechanisms carry odds p/(1-p). The product of all (1-p)
    cancels when comparing the two logical classes. A negative sign encodes
    odd logical flips, so the sum is proportional to P(s,0) - P(s,1) within
    the truncation. The truncation and fallback make this approximate ML.
    """
    def __init__(self, circuit, split_temporally=False):
        if circuit.num_observables != 1:
            raise ValueError("Requires one logical observable.")
        self.n = circuit.num_detectors
        self.fallback = pymatching.Matching.from_detector_error_model(
            circuit.detector_error_model(decompose_errors=True))
        rates = {}
        for op in circuit.detector_error_model().flattened():
            if op.type != "error":
                continue
            mask, logical = 0, 0
            for target in op.targets_copy():
                if target.is_relative_detector_id():
                    mask ^= 1 << target.val
                elif target.is_logical_observable_id():
                    logical ^= 1
            p = op.args_copy()[0]
            prev = rates.get((mask,logical), 0.0)
            rates[mask,logical] = p + prev - 2*p*prev
        # Undetectable independent mechanisms multiply the exact class
        # difference by a syndrome-independent factor.
        self.invert = rates.get((0,1),0) > 0.5
        self.signed = defaultdict(float)
        self.by_detector = [[] for _ in range(self.n)]
        for (mask,logical),p in rates.items():
            if mask:
                if not 0 <= p < .5:
                    raise ValueError("Each nonempty fault signature must have probability below 0.5.")
                self.signed[mask] += (-1 if logical else 1)*p/(1-p)
        for mask in self.signed:
            bits = mask
            while bits:
                low = bits & -bits
                self.by_detector[low.bit_length()-1].append(mask)
                bits ^= low
        self.max_weight = max((s.bit_count() for s in self.signed), default=0)
        self.prediction = lru_cache(maxsize=65536)(self._predict_one)

        self.split_temporally = split_temporally
        if split_temporally:
            coords = circuit.get_detector_coordinates()
            if any(i not in coords or len(coords[i]) < 3 for i in range(self.n)):
                raise ValueError("Temporal splitting requires detector (x, y, t) coordinates.")
            self.times = [coords[i][-1] for i in range(self.n)]
            if sorted(self.times) != self.times:
                raise ValueError("Detectors must be ordered by round.")
            span = max((self.times[m.bit_length()-1]-self.times[(m & -m).bit_length()-1]
                        for m in self.signed), default=0)
            self.split_gap = max(3, 2*span)

    def _parts(self, s):
        """Split separated groups of fired detectors for a local approximation."""
        part = 0
        previous = -float("inf")
        while s:
            low = s & -s
            t = self.times[low.bit_length()-1]
            if part and t-previous > self.split_gap:
                yield part
                part = 0
            part |= low
            previous = t
            s ^= low
        if part:
            yield part

    def _predict_one(self,s):
        if not s:
            # Empty-syndrome prefers the zero-fault explanation in this model.
            return int(self.invert)
        if s.bit_count() > 2*self.max_weight:
            return -1
        anchor = (s & -s).bit_length()-1
        difference = self.signed.get(s,0.0)
        for first in self.by_detector[anchor]:
            second = s ^ first
            difference += self.signed[first]*self.signed.get(second,0.)
        if difference == 0:
            return -1
        return int(difference<0) ^ int(self.invert)

    def decode_batch(self, events, **kwargs):
        if events.ndim != 2 or events.shape[1] != self.n:
            raise ValueError("Mismatched detector count.")
        packed = np.packbits(events, axis=1, bitorder="little")
        integers = [int.from_bytes(row, "little") for row in packed]
        estimates = np.fromiter(map(self.prediction, integers), dtype=np.int8,count=len(events))
        unknown = estimates == -1
        if unknown.any() and self.split_temporally:
            # Retain whole-shot MWPM on unresolved clusters. Remove only temporal
            # islands which our bounded likelihood model can explain.
            residual = packed[unknown].copy()
            parity = np.zeros(len(residual), dtype=np.uint8)
            for j,i in enumerate(np.flatnonzero(unknown)):
                parts = list(self._parts(integers[i]))
                if len(parts) < 2:
                    continue
                missing = 0
                for part in parts:
                    estimate = self.prediction(part)
                    if estimate < 0:
                        missing |= part
                    else:
                        parity[j] ^= estimate
                residual[j] = np.frombuffer(missing.to_bytes(packed.shape[1],"little"),dtype=np.uint8)
            det = np.unpackbits(residual, axis=1, count=self.n, bitorder="little")
            estimates[unknown] = parity ^ self.fallback.decode_batch(det)[:,0]
        elif unknown.any():
            estimates[unknown] = self.fallback.decode_batch(events[unknown])[:,0]
        return estimates.astype(np.uint8).reshape(-1,1)
