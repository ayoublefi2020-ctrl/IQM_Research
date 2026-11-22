"""Compile a no-reset Qiskit memory for IQM Emerald, execute it, and decode the counts."""
import argparse
import getpass
import json
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path

from qiskit import transpile
from qiskit.transpiler import CouplingMap

from build_emerald_qubit_rotated import build_emerald_qubit_map, calibrated_layout
from extract_syndromes import extract_syndromes
from internal_helpers import counts_to_measurement_array
from native_memory import make_native_memory, PROFILES as NATIVE_PROFILES, SCHEDULES
from qec_analysis import PROFILES, failures, fit_rate, matcher, noise_model, plot_curves, wilson
from stim_to_qiskit import stim_to_qiskit
from surface_code import make_stim_circuit

SERVER_URL = "https://resonance.iqm.tech"
DEFAULT_SELECTION = Path(__file__).resolve().parent / "results" / "optimization" / "final_choice.json"


def connect(token=None, device="emerald", use_metrics=True, calibration_set_id=None):
    from iqm.qiskit_iqm import IQMProvider
    credential = token or os.environ.get("IQM_TOKEN")
    auth = {} if os.environ.get("IQM_TOKEN") and token is None else {"token": credential or getpass.getpass("IQM token: ")}
    provider = IQMProvider(SERVER_URL, quantum_computer=device, **auth)
    calibration = {"calibration_set_id": calibration_set_id} if calibration_set_id else {}
    if use_metrics:
        try:
            return provider.get_backend(use_metrics=True, **calibration)
        except Exception:
            # Some Resonance endpoints expose connectivity without quality metrics.
            backend = provider.get_backend(use_metrics=False, **calibration)
            warnings.warn("Connected to IQM using connectivity and assumed noise rates because the metrics-enabled target was unavailable.")
            return backend
    return provider.get_backend(use_metrics=False, **calibration)


def memory(distance, rounds, basis, model, schedule, p, profile):
    if model == "native":
        return make_native_memory(distance, rounds, basis, schedule, p, profile)
    if model != "legacy":
        raise ValueError("Choose native or legacy circuit model")
    return make_stim_circuit(distance, rounds, basis, noise=noise_model(p, profile))


def prepare(distance, rounds, basis, backend=None, *, noise_family="legacy", schedule="forward",
            profile=None, fixed_layout=None, candidate_limit=1024, preserve_ticks=False):
    profile = profile or ("balanced" if noise_family == "native" else "uniform")
    circuit = memory(distance, rounds, basis, noise_family, schedule, 0., profile)
    layout_audit = None
    qc, _, _ = stim_to_qiskit(circuit, preserve_ticks=preserve_ticks)
    if backend is None:
        # The README documents a 5x5 patch within Emerald, with a row stride of 8.
        grid = [[40-8*r+c for c in range(5)] for r in range(5)]
        edges = [(grid[r][c],grid[s][t]) for r in range(5) for c in range(5)
                 for s,t in ((r+1,c),(r,c+1)) if s<5 and t<5]
        coupling = CouplingMap(edges + [(b,a) for a,b in edges])
        layout = list(build_emerald_qubit_map(circuit).values())
        kw = dict(coupling_map=coupling,basis_gates=["rz","sx","x","cz"])
    else:
        if fixed_layout is None:
            layout, layout_audit = calibrated_layout(qc, backend, candidate_limit)
        else:
            layout = fixed_layout
        kw = dict(backend=backend)
    compiled = transpile(qc,initial_layout=layout,routing_method="none",optimization_level=1,
                         seed_transpiler=19,**kw)
    ops = dict(compiled.count_ops())
    if ops.get("reset",0) or ops.get("swap",0) or ops.get("measure",0)!=circuit.num_measurements:
        raise ValueError(f"Unexpected compiled circuit: {ops}")
    if backend is not None:
        # The real adapter validates all native loci and serializes measurement keys here.
        if hasattr(backend.target, "iqm_dqa"):
            from iqm.qiskit_iqm.iqm_circuit_validation import validate_circuit
            validate_circuit(compiled, backend)
    return circuit,compiled,dict(layout=layout,layout_search=layout_audit,depth=compiled.depth(),operations=ops,
                                 routing="disabled",unique_required_pairs=len(set(
                                     tuple(sorted(qc.find_bit(q).index for q in op.qubits))
                                     for op in qc.data if op.operation.num_qubits==2)))


def build_decoder(model, name):
    if name in ("likelihood", "local_likelihood"):
        from likelihood_decoder import FaultLikelihoodDecoder
        return FaultLikelihoodDecoder(model, split_temporally=(name == "local_likelihood"))
    return matcher(model, name)


def decode_hardware_results(syndromes, model_circuit, decoder="plain", *, prepared_decoder=None):
    graph = prepared_decoder if prepared_decoder is not None else build_decoder(model_circuit, decoder)
    events, observed = syndromes["det_events"], syndromes["obs_flips"]
    if decoder in ("likelihood", "local_likelihood"):
        predicted = graph.decode_batch(events)
        if predicted.shape != observed.shape:
            raise ValueError("Decoder and observable dimensions disagree")
        errors = (predicted != observed).any(axis=1)
    else:
        errors = failures(graph, decoder, events, observed)
    k,n = int(errors.sum()),len(errors)
    return dict(failures=k,shots=n,probability=k/n,interval95=wilson(k,n))


def process_counts(counts, circuit, shots):
    raw = counts_to_measurement_array(counts,circuit.num_measurements,shots)
    return extract_syndromes(raw,circuit,print_summary=False)


def run_qiskit(distance=3, rounds=1, shots=5000, token=None, quantum_computer="emerald",
               no_reset=True, basis="Z"):
    if not no_reset:
        raise ValueError("The hardware track requires no-reset operation.")
    backend = connect(token,quantum_computer)
    selection = json.loads(DEFAULT_SELECTION.read_text(encoding="utf-8-sig"))
    c,qc,_ = prepare(distance,rounds,basis,backend,noise_family=selection["noise_model"],
                     schedule=selection["schedule"],profile=selection["profile"])
    return process_counts(backend.run(qc,shots=shots).result().get_counts(),c,shots)


def backend_mode(args):
    return args.iqm_fake or args.live_compile or args.submit


def run(args):
    config = json.loads(Path(args.selection).read_text(encoding="utf-8-sig"))
    decoder = args.decoder or config["selected_decoder"]
    if decoder not in ("correlated", "plain", "likelihood", "local_likelihood"):
        raise ValueError(f"Unknown selected decoder: {decoder}")
    family = args.noise_model or config.get("noise_model", "legacy")
    profile = args.profile or config.get("profile") or ("balanced" if family == "native" else "uniform")
    schedule = args.schedule or config.get("schedule", "forward")
    p = args.p if args.p is not None else config.get("p", .003)
    profiles = NATIVE_PROFILES if family == "native" else PROFILES
    if profile not in profiles or not 0 < p < .5 / max(profiles[profile]):
        raise ValueError(f"Invalid decoder profile or noise strength for {family}: {profile}, {p}")
    use_round_policy = (args.decoder is None and args.distance==config.get("distance")
                        and args.basis==config.get("basis") and p==config.get("p")
                        and profile==config.get("profile") and schedule==config.get("schedule")
                        and family==config.get("noise_model"))
    by_round = config.get("decoder_by_round", {}) if use_round_policy else {}
    weights = args.decoder_weights or ("target" if family=="native" and backend_mode(args) else "profile")
    if weights=="target" and (family!="native" or not backend_mode(args)):
        raise ValueError("Target decoder weights require the native circuit and an IQM backend.")
    if args.iqm_fake:
        from iqm.qiskit_iqm.fake_backends import IQMFakeAphrodite
        backend = IQMFakeAphrodite()
    elif args.submit or args.live_compile:
        backend = connect(device=args.device,use_metrics=not args.no_metrics)
    else:
        backend = None
    out = Path(args.output)/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True)
    def save(name,data):
        (out/name).write_text(json.dumps(data,indent=2))
    save("settings.json",dict(vars(args), selected_decoder=decoder, noise_model=family,
                              schedule=schedule, p=p, profile=profile, decoder_by_round=by_round, decoder_weights=weights))
    # The same physical qubits must be used at every round count for a rate fit.
    prepare_options = dict(noise_family=family, schedule=schedule, profile=profile,
                           preserve_ticks=getattr(args,"preserve_ticks",False))
    if backend is not None:
        reference = memory(args.distance, max(args.rounds), args.basis, family, schedule, 0., profile)
        logical, _, _ = stim_to_qiskit(reference)
        fixed, audit = calibrated_layout(logical, backend, args.layout_candidates)
        save("layout-search.json", dict(audit, reference_rounds=max(args.rounds),
                                       calibration_set=str(getattr(getattr(backend,"architecture",None),"calibration_set_id",None))))
        prepare_options["fixed_layout"] = fixed
    points = []
    for r in args.rounds:
        round_decoder = by_round.get(str(r), decoder)
        if args.simulate:
            model=memory(args.distance,r,args.basis,family,schedule,p,profile)
            events,observed=model.compile_detector_sampler(seed=args.seed+r).sample(
                args.shots,separate_observables=True)
            stats=decode_hardware_results(dict(det_events=events,obs_flips=observed),model,round_decoder)
            save(f"errors-r{r}.json",dict(stats,decoder=round_decoder,rounds=r))
            points.append((r,stats["failures"],stats["shots"]))
            print(f"rounds={r} failures={stats['failures']}/{args.shots} P_L={stats['probability']:.4%}")
            continue
        c, qc, meta = prepare(args.distance,r,args.basis,backend,**prepare_options)
        if weights=="target":
            from device_noise import mapped_decoder_model
            model,meta["prior"]=mapped_decoder_model(c,backend,meta["layout"],p,profile)
        else:
            model=memory(args.distance,r,args.basis,family,schedule,p,profile)
        graph=build_decoder(model,round_decoder)
        model.to_file(str(out/f"decoder-r{r}.stim"))
        save(f"layout-r{r}.json",dict(meta,decoder=round_decoder))
        print(f"rounds={r} depth={meta['depth']} operations={meta['operations']}",flush=True)
        if args.live_compile:
            backend.create_run_request(qc,shots=args.shots)
        if not args.submit:
            continue
        job = backend.run(qc,shots=args.shots)
        job_id = job.job_id()
        save(f"job-r{r}.json",dict(job_id=job_id))
        result = job.result()
        counts = result.get_counts()
        executed_calibration = getattr(result.results[0],"calibration_set_id",None)
        save(f"counts-r{r}.json",dict(counts=counts,job_id=job_id,
             calibration_set=str(executed_calibration) if executed_calibration is not None else None))
        syn = process_counts(counts,c,args.shots)
        stats = decode_hardware_results(syn,model,round_decoder,prepared_decoder=graph)
        save(f"errors-r{r}.json",dict(stats,decoder=round_decoder,detector_rates=syn["detector_firing_rate"].tolist()))
        points.append((r,stats["failures"],stats["shots"]))
        print(stats,flush=True)
    if len(points)>1:
        cols = list(zip(*points))
        print("Fitted rate per round:",fit_rate(*cols))
        save("fit.json",fit_rate(*cols))
        plot_curves({("round-specific" if by_round else decoder):cols},out/("simulation.png" if args.simulate else "hardware.png"),
                    f"{'Simulation' if args.simulate else args.device}, d={args.distance}, {args.basis} memory")
    print("Output:",out)


if __name__ == "__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    mode=ap.add_mutually_exclusive_group()
    mode.add_argument("--live-compile",action="store_true",help="Check the actual target without submitting.")
    mode.add_argument("--simulate",action="store_true",help="Run the selected memory and decoder locally in Stim.")
    ap.add_argument("--seed",type=int,default=421815,help="Base seed for --simulate.")
    mode.add_argument("--iqm-fake", action="store_true", help="Compile and validate on IQM's local 54-qubit fixture.")
    ap.add_argument("--no-metrics", action="store_true", help="Use connectivity only if live quality metrics are unavailable.")
    ap.add_argument("--layout-candidates", type=int, default=1024)
    ap.add_argument("--schedule", choices=SCHEDULES)
    ap.add_argument("--preserve-ticks",action="store_true",help="Preserve Stim layer boundaries as IQM barriers.")
    ap.add_argument("--noise-model", choices=["native","legacy"])
    mode.add_argument("--submit",action="store_true",help="Submit one real job per round count.")
    ap.add_argument("--distance",type=int,default=3)
    ap.add_argument("--basis",choices=["X","Z"],default="Z")
    ap.add_argument("--rounds",type=int,nargs="+",default=[2,3,5,8])
    ap.add_argument("--device",default="emerald")
    ap.add_argument("--shots",type=int,default=5000)
    ap.add_argument("--p",type=float,help="Assumed decoder noise strength.")
    ap.add_argument("--profile",choices=sorted(set(PROFILES) | set(NATIVE_PROFILES)))
    ap.add_argument("--decoder-weights",choices=["profile","target"],
                    help="For native circuits use available IQM target metrics by default.")
    ap.add_argument("--selection",default=str(DEFAULT_SELECTION))
    ap.add_argument("--decoder",choices=["plain","correlated","likelihood","local_likelihood"])
    ap.add_argument("--output",default="results/hardware")
    args=ap.parse_args()
    if args.shots<1 or len(set(args.rounds))!=len(args.rounds) or min(args.rounds)<1 or args.layout_candidates<1:
        ap.error("Use positive shots, distinct rounds and a positive layout candidate limit.")
    run(args)
