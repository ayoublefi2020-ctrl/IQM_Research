import json
from pathlib import Path
from html import escape

root=Path("research_data/hardware_characterization")
t=json.loads((root/"topology.json").read_text())
for distance in (3,5):
    layout=set(t["distances"][str(distance)].get("layout",[]))
    supported=t["distances"][str(distance)]["exact_patch"]
    label=f"Distance {distance} - "+("exact live patch selected" if supported else "no exact live patch")
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="465" viewBox="0 0 760 465">',
         '<rect width="760" height="465" fill="#132338"/>',
         f'<text x="20" y="26" fill="white" font-family="Arial" font-size="19">{label}</text>','<g transform="translate(15 40)">']
    for a,b in t["edges"]:
        x1,y1=t["positions"][a]
        x2,y2=t["positions"][b]
        color="#55cfc5" if a in layout and b in layout else "#426282"
        svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}"/>')
    for i,(x,y) in enumerate(t["positions"]):
        color="#55cfc5" if i in layout else "#7795ad"
        svg.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{color}"/>')
        svg.append(f'<text x="{x+6}" y="{y-4}" fill="#aabbd0" font-size="10" font-family="Arial">{escape(t["qubits"][i])}</text>')
    svg.extend((" </g>",f'<text x="20" y="450" fill="#aabbd0" font-family="Arial" font-size="11">Emerald CZ calibration {t["calibration"]}. Diagram positions are schematic.</text>',"</svg>"))
    (root/f"distance_{distance}_connectivity.svg").write_text("\n".join(svg),encoding="utf-8")
