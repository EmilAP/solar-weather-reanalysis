from __future__ import annotations

import json

from common import ROOT, load_sources, make_logger, write_manifest


def main() -> int:
    logger = make_logger("07_prepare_era5_requests")
    cfg = load_sources()["era5"]
    raw_dir = ROOT / "data" / "raw" / "era5"

    request_template = {
        "product_type": ["reanalysis"],
        "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind", "mean_sea_level_pressure"],
        "year": [str(y) for y in cfg["years"]],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "format": "netcdf",
    }

    request_path = raw_dir / "era5_request_template.json"
    request_path.write_text(json.dumps(request_template, indent=2), encoding="utf-8")

    env_template = raw_dir / ".cdsapirc.template"
    env_template.write_text(
        "url: https://cds.climate.copernicus.eu/api/v2\n"
        "key: <your-uid>:<your-api-key>\n",
        encoding="utf-8",
    )

    python_template = raw_dir / "download_era5_template.py"
    python_template.write_text(
        "import cdsapi\n\n"
        "c = cdsapi.Client()\n"
        "c.retrieve(\n"
        f"    '{cfg['dataset']}',\n"
        "    {\n"
        "        # Copy fields from era5_request_template.json and adjust scope before running\n"
        "    },\n"
        "    'era5_output.nc'\n"
        ")\n",
        encoding="utf-8",
    )

    payload = {
        "script": "07_prepare_era5_requests.py",
        "outputs": [
            str(request_path.relative_to(ROOT)),
            str(env_template.relative_to(ROOT)),
            str(python_template.relative_to(ROOT)),
        ],
        "docs_url": cfg["cds_api_docs"],
        "ok": True,
        "manual_required": True,
    }
    write_manifest("07_prepare_era5_requests", payload)
    logger.info("Prepared ERA5 request templates only; no download executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
