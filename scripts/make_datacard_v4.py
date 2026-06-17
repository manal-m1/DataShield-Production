from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    out = ROOT / "services" / "immuneguard-serv" / "DataCard_v4.xlsx"

    # CDC: c1/c2 mapping is expected in a sheet named "Mapping_C1_C2"
    # (we keep a small minimal subset needed for validation).
    mapping = pd.DataFrame(
        {
            "Secteur d'activité": [
                "Ressources Humaines / Emploi",
                "Ressources Humaines",
                "Santé",
            ],
            "c1": [1.0, 1.0, 1.0],
            "Finalité du traitement": [
                "Decision automatisee",
                "Prendre une décision automatisée",
                "Reconnaissance faciale",
            ],
            "c2": [1.0, 1.0, 1.0],
        }
    )

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        mapping.to_excel(writer, sheet_name="Mapping_C1_C2", index=False)

    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

