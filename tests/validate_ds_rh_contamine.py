from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IMMUNEGUARD_SVC = ROOT / "services" / "immuneguard-serv"


def _ensure_imports() -> None:
    sys.path.insert(0, str(IMMUNEGUARD_SVC))


@dataclass(frozen=True)
class ExpectRange:
    min_value: float
    max_value: float


def _in_range(label: str, value: float, exp: ExpectRange) -> tuple[bool, str]:
    ok = exp.min_value <= value <= exp.max_value
    return ok, f"{label}={value:.4f} expected in [{exp.min_value}, {exp.max_value}]"


def _equals(label: str, value: float, expected: float, tol: float = 1e-9) -> tuple[bool, str]:
    ok = abs(value - expected) <= tol
    return ok, f"{label}={value:.4f} expected {expected:.4f}"


def main() -> int:
    # Avoid Windows console encoding crashes (e.g., "→" in XAI templates)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    _ensure_imports()

    from core.risk_analysis import build_xai, compute_c_factor, compute_score_b, compute_score_i  # noqa: WPS433
    from core.attack.attack import compute_succ, get_attack_config_from_profile  # noqa: WPS433
    from core.vulnerabilte.checks import run_all_checks_with_profile  # noqa: WPS433

    # Pick the latest uploaded ds_rh_contamine.csv
    uploads_dir = ROOT / "services" / "cleaning-serv" / "storage" / "uploads"
    candidates = sorted(uploads_dir.glob("*_ds_rh_contamine.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        print("ERROR: ds_rh_contamine.csv not found under cleaning-serv storage uploads")
        return 2

    csv_path = candidates[0]
    df = pd.read_csv(csv_path)

    # DataCard: secteur = RH / Emploi, finalite = Decision automatisee
    profile = {
        "dataset_id": "local_ds_rh_contamine",
        "dataset_name": "ds_rh_contamine",
        "secteur": "Ressources Humaines / Emploi",
        "Secteur d'activité": "Ressources Humaines / Emploi",
        "Finalité du traitement": "Decision automatisee",
        # Minimal analysis profile for Score A routines
        "attacks": {
            "quasi_identifiers": ["nom", "ville"],  # conservative minimal set
            "sensitive_attribute": "genre",
            "public_sample_frac": 0.15,
        },
        "checks": {
            "imbalance_columns": ["nom", "ville"],
            "correlation_columns": [],
            "id_column": None,
            "pii_columns": ["nom"],
            "sensitive_health_columns": [],
        },
        # No masking in this validation run
        "masked_columns": [],
    }

    b = compute_score_b(df, profile)
    i = compute_score_i(df, profile)
    c = compute_c_factor(profile)

    attack_cfg = get_attack_config_from_profile(profile)
    succ = compute_succ(df, attack_cfg)
    vuln = run_all_checks_with_profile(df, profile)
    a = 0.50 * float(succ["Succ"]) + 0.50 * float(vuln["Vuln"])

    r_base = 0.20 * float(b["B"]) + 0.60 * float(a) + 0.20 * float(i["I"])
    r_final = 100.0 * min(1.0, r_base * float(c["C"]))
    xai = build_xai(df, profile, i)

    # Print raw results (useful for debugging)
    print(f"CSV={csv_path.name} rows={len(df)} cols={len(df.columns)}")
    print("COLUMNS=", list(df.columns))
    print("Score B:", b)
    print(
        "Score A:",
        round(a, 4),
        "Succ",
        round(float(succ["Succ"]), 4),
        "Vuln",
        round(float(vuln["Vuln"]), 4),
        "Singling",
        succ.get("taux_singling"),
        "Inference",
        succ.get("taux_inference"),
    )
    print("Score I:", i)
    print("C factor:", c)
    print("R_base:", round(r_base, 4), "R_final:", round(r_final, 2))
    print("XAI_count:", len(xai))
    for item in xai[:10]:
        print("XAI:", item.get("signal"), item.get("column"), item.get("severity"), item.get("explanation"))

    # Validation checks (as per delivery gate)
    checks: list[tuple[str, bool, str]] = []
    ok, msg = _in_range("b1", float(b["b1"]), ExpectRange(0.3, 0.9))
    checks.append(("1) Score B — b1", ok, msg))
    ok, msg = _in_range("b2", float(b["b2"]), ExpectRange(0.4, 1.0))
    checks.append(("2) Score B — b2", ok, msg))
    ok, msg = _in_range("B", float(b["B"]), ExpectRange(0.35, 0.75))
    checks.append(("3) Score B — total", ok, msg))
    ok, msg = _in_range("A", float(a), ExpectRange(0.45, 0.70))
    checks.append(("4) Score A", ok, msg))
    ok, msg = _in_range("I", float(i["I"]), ExpectRange(0.10, 0.70))
    checks.append(("5) Score I — secteur RH", ok, msg))
    ok, msg = _equals("C", float(c["C"]), 1.40, tol=1e-6)
    checks.append(("6) Facteur C", ok, msg))
    ok, msg = _in_range("R_base", float(r_base), ExpectRange(0.30, 0.70))
    checks.append(("7) R_base", ok, msg))
    ok, msg = _in_range("R_final", float(r_final), ExpectRange(40.0, 100.0))
    checks.append(("8) R_final", ok, msg))
    ok = len(xai) >= 2 and any(it.get("signal") == "S_prot" for it in xai) and any(it.get("signal") == "S_dec" for it in xai)
    checks.append(("9) Explications XAI", ok, f"xai_count={len(xai)} requires >=2 incl S_prot and S_dec"))

    print("\n--- VALIDATION ---")
    failed = 0
    for title, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status} {title}: {detail}")
        if not passed:
            failed += 1

    if failed:
        print(f"\nDELIVERY GATE: FAIL ({failed} failing checks)")
        return 1

    print("\nDELIVERY GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

