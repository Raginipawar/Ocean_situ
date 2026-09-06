"""Run the Checkpoint 7 end-to-end model pipeline in local demo mode."""

from __future__ import annotations

from varuna_model_pipeline.pipeline import load_local_demo_model_data


def main() -> None:
    result = load_local_demo_model_data()
    ds = result.dataset
    print("source:", result.source.value)
    print("attempts:", [f"{a.source.value}:{'ok' if a.ok else 'failed'}" for a in result.attempts])
    print("stages:", result.stages)
    print("dims:", dict(ds.sizes))
    print("variables:", list(ds.data_vars))
    print("processing_level:", ds.attrs.get("processing_level"))


if __name__ == "__main__":
    main()

