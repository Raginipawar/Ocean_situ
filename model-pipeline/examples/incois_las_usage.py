"""Usage example for Checkpoint 2 INCOIS LAS ingestion.

Run from the repository root after installing the model-pipeline dependencies:

    $env:PYTHONPATH='model-pipeline\\src'
    python model-pipeline\\examples\\incois_las_usage.py path\\to\\incois.nc
"""

from __future__ import annotations

import sys

from varuna_model_pipeline.sources.incois_las import IncoisLasIngestor


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: incois_las_usage.py <path-or-url-to-netcdf>")

    result = IncoisLasIngestor().load(sys.argv[1])
    print("source:", result.source.value)
    print("source_path:", result.source_path)
    print("coordinate_mapping:", result.coordinate_mapping)
    print("variable_mapping:", result.variable_mapping)
    print("dataset variables:", list(result.dataset.data_vars))
    print("dataset attrs:", result.dataset.attrs)


if __name__ == "__main__":
    main()

