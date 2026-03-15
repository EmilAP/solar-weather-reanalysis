from __future__ import annotations

import pandas as pd

from _utils import load_config, make_logger, write_dataframe, write_script_manifest


def main() -> int:
    logger = make_logger("18_detect_cir_hss_events")
    cfg = load_config()
    daily = pd.read_csv("data/derived/daily/omni_daily.csv", parse_dates=["date"])

    speed = daily["speed_mean"]
    speed_jump = speed.diff()
    hss = daily.loc[
        (speed >= cfg["cir_hss"]["hss_speed_threshold"]) & (speed_jump >= cfg["cir_hss"]["hss_speed_jump_threshold"]),
        ["date", "speed_mean", "proton_density_mean", "b_mag_mean", "flow_pressure_mean"],
    ].copy()
    hss["event_type"] = "hss_onset"

    cir = hss.loc[
        (hss["proton_density_mean"] >= cfg["cir_hss"]["cir_density_threshold"])
        | (hss["b_mag_mean"] >= cfg["cir_hss"]["cir_bmag_threshold"])
        | (hss["flow_pressure_mean"] >= cfg["cir_hss"]["cir_pressure_threshold"])
    ].copy()
    cir["event_type"] = "cir_proxy"

    combined = pd.concat([hss, cir], ignore_index=True).sort_values(["date", "event_type"])
    outputs = {
        "hss": write_dataframe(hss, "data/derived/catalogs/hss_onset_catalog"),
        "cir": write_dataframe(cir, "data/derived/catalogs/cir_proxy_catalog"),
        "combined": write_dataframe(combined, "data/derived/catalogs/cir_hss_catalog"),
    }
    metrics = {
        "hss_count": int(len(hss)),
        "cir_count": int(len(cir)),
    }
    write_script_manifest(
        "18_detect_cir_hss_events.py",
        ["data/derived/daily/omni_daily.csv"],
        outputs,
        metrics,
        assumptions=["CIR/HSS events are simple transparent proxies based on speed rise plus compression signatures."],
    )
    logger.info("Detected %d HSS onsets and %d CIR proxies", len(hss), len(cir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
