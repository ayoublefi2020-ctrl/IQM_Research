"""Check whether improving a layout score improves decoded memory in a device-shaped noise model."""
import csv
import json
from pathlib import Path
import numpy as np
from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
from native_memory import make_native_memory
from build_emerald_qubit_rotated import calibrated_layout
from device_noise import mapped_decoder_model
from run_on_hardware import build_decoder
from stim_to_qiskit import stim_to_qiskit

OUT=Path("results/optimization")


if __name__=="__main__":
    settings=json.loads((OUT/"final_choice.json").read_text())
    schedule=settings["schedule"]
    decoder=settings["selected_decoder"]
    backend=IQMFakeAphrodite()
    rows=[]
    for basis in "ZX":
        reference=make_native_memory(3,25,basis,schedule)
        _,audit=calibrated_layout(stim_to_qiskit(reference)[0],backend)
        for label in ("first_exact","selected"):
            placement=audit[label]
            for r in (3,8,16,25):
                clean=make_native_memory(3,r,basis,schedule)
                model,_=mapped_decoder_model(clean,backend,placement["layout"],.003,"balanced")
                seed=981003+len(rows)
                det,obs=model.compile_detector_sampler(seed=seed).sample(30000,separate_observables=True)
                row=dict(basis=basis,layout=label,score=placement["score"],rounds=r,shots=len(det),seed=seed)
                for key,prior in (("fixture_weights",model),("balanced_weights",make_native_memory(3,r,basis,schedule,.003))):
                    prediction=build_decoder(prior,decoder).decode_batch(det)
                    row[key]=int(np.count_nonzero(prediction!=obs))
                rows.append(row)
    with (OUT/"fixture_noise.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
