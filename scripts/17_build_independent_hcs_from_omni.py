from __future__ import annotations

import pandas as pd

from _utils import ROOT, make_logger, write_dataframe, write_script_manifest


def main() -> int:
    logger = make_logger("17_build_independent_hcs_from_omni")
    path = ROOT / "data/derived/catalogs/hcs_from_omni.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path}: run 26_reconstruct_hcs_from_omni.py first.")
    catalog = pd.read_csv(path, parse_dates=["date"])
    if catalog.empty or catalog["date"].isna().any() or catalog["date"].duplicated().any():
        raise ValueError("The canonical daily-Bx HCS catalog must contain unique valid dates.")
    catalog["datetime_utc"] = pd.to_datetime(catalog["date"], utc=True)
    catalog["year"] = catalog["datetime_utc"].dt.year
    outputs = {"catalog": write_dataframe(catalog, "data/derived/catalogs/independent_hcs_catalog")}
    write_script_manifest(
        "17_build_independent_hcs_from_omni.py", [path], outputs,
        {"event_count": len(catalog)},
        assumptions=[
            "Compatibility export of the canonical daily-Bx reconstruction from script 26.",
            "The former sign(-Bx*By) proxy is retired because it is invariant under simultaneous sector reversal.",
        ],
    )
    logger.info("Exported %d canonical daily-Bx crossings", len(catalog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
