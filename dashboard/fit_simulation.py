import json
from pathlib import Path
import numpy as np
from scipy.special import xlogy
from scipy.stats import chi2
from qec_analysis import fit_rate, probability

def compare(root):
    fits={}
    for distance in (3,5):
        rows=[json.loads(p.read_text()) for p in (root/f"distance_{distance}/simulations").glob("*.json")]
        points=sorted((r for r in rows if r["settings"]["seed"]==51226 and r["settings"]["profile"]=="balanced"),
                      key=lambda r:r["rounds"])
        if [r["rounds"] for r in points]!=[3,5,20]:
            raise ValueError("Expected one matched simulation per distance at rounds 3, 5 and 20")
        rounds, counts, shots=(np.array([item[key] for item in points]) for key in ("rounds","failures","shots"))
        fit=fit_rate(rounds,counts,shots)
        expected=probability(rounds,fit["rate"])
        deviance=2*sum(xlogy(counts,counts/(shots*expected))+xlogy(shots-counts,(shots-counts)/(shots*(1-expected))))
        fits[str(distance)]=dict(fit,goodness_p=float(chi2.sf(deviance,len(points)-1)),points=[a["id"] for a in points])
    return fits

if __name__=="__main__":
    root=Path("research_data")
    (root/"distance_5/validation_fits.json").write_text(json.dumps(compare(root),indent=2),encoding="utf-8")
