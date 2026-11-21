"""Translate available device error metrics into a Pauli prior for offline decoding."""
from collections import Counter

import stim
from build_emerald_qubit_rotated import calibration_errors
from internal_helpers import get_qubit_lists
from native_memory import PROFILES


def mapped_decoder_model(clean,backend,layout,p,profile):
    h,cz,prep,readout,idle = (p*x for x in PROFILES[profile])
    edge_errors,ro_errors,source=calibration_errors(backend)
    sparse=sorted(clean.get_final_qubit_coordinates())
    physical=dict(zip(sparse,layout,strict=True))
    one_errors={}
    if "r" in backend.target.operation_names:
        for locus,props in backend.target["r"].items():
            error=getattr(props,"error",None)
            if locus and error is not None and 0 <= error < .5:
                one_errors[locus[0]]=error
    if not one_errors and hasattr(backend,"error_profile"):
        for q,lam in backend.error_profile.single_qubit_gate_depolarizing_error_parameters["prx"].items():
            one_errors[backend.qubit_name_to_index(q)]=.5*lam
    # For an n-qubit depolarizing Pauli channel, p = (2**n+1)/2**n * average infidelity.
    counters=Counter()
    def rate(mapping,key,factor,base,label):
        measured=mapping.get(key)
        if measured is not None and 0 <= factor*measured < .5:
            counters[label+"_from_target"]+=1
            return factor*measured
        counters[label+"_from_profile"]+=1
        return base
    data,anc=get_qubit_lists(clean)
    out=stim.Circuit()
    for op in clean:
        qs=[t.value for t in op.targets_copy()]
        if op.name=="M":
            if set(anc).intersection(qs) and idle:
                out.append("Z_ERROR" if profile=="phase" else "DEPOLARIZE1",data,idle)
            for q in qs:
                out.append("M",[q],rate(ro_errors,(physical[q],),1,readout,"readout"))
        else:
            out.append(op)
            if op.name=="H":
                for q in qs:
                    out.append("DEPOLARIZE1",[q],rate(one_errors,physical[q],1.5,h,"rotation"))
            elif op.name=="CZ":
                for a,b in zip(qs[::2],qs[1::2]):
                    key=tuple(sorted((physical[a],physical[b])))
                    out.append("DEPOLARIZE2",[a,b],rate(edge_errors,key,1.25,cz,"cz"))
            elif op.name=="R" and prep:
                out.append("X_ERROR",qs,prep)
    return out,dict(metric_source=source,counts=dict(counters),idle_and_preparation="assumed profile")
