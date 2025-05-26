import argparse
import os
import json
import random
import shutil


def sample_medonc(datadir: str, num: int):
    import pandas as pd

    patients = pd.read_parquet(
        os.path.join(datadir, "patients.pq"), columns=["sex"]
    )
    lines = pd.read_parquet(os.path.join(datadir, "lines.pq"), columns=["id"])
    updates = pd.read_parquet(
        os.path.join(datadir, "updates.pq"), columns=["line_id", "bsa"]
    )
    medicine = pd.read_parquet(
        os.path.join(datadir, "medicine.pq"), columns=["update_id"]
    )

    out = []
    d = (
        medicine.merge(
            updates,
            left_on="update_id",
            right_index=True,
            how="inner",
        )
        .merge(lines, left_on="line_id", right_index=True, how="inner")
        .merge(
            patients,
            left_on="id",
            right_index=True,
            how="inner",
        )[["id", "bsa"]]
    )

    vc = d['id'].value_counts()
    long_enough = set(vc[vc >= 3].index)
    has_bsa = set(d["id"][~pd.isna(d["bsa"])])

    ids = sorted(long_enough.intersection(has_bsa))
    out.extend(random.sample(ids, num))

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--name", help="Round name (e.g., 00_tutorial.json)", required=True
    )
    parser.add_argument(
        "--pretty",
        help='Pretty name (e.g., "Experiment 1 (100 patients)")',
        required=True,
    )
    parser.add_argument("--experiment", help="Manually specify experiment")
    parser.add_argument("--samples", help="Round samples per dataset", default=25)
    parser.add_argument(
        "--samples-orig", help="Round samples per dataset", default=None, type=int
    )
    parser.add_argument(
        "--peek",
        help="Whether to show results to users",
        action="store_true",
        default=False,
    )

    parser.add_argument("-d", "--experiments-dir", default="./experiments")

    args = parser.parse_args()

    name = args.name
    pretty = args.pretty
    peek = args.peek
    samples_per = int(args.samples)
    samples_per_orig = int(args.samples_orig) if args.samples_orig else samples_per
    expdir = args.experiments_dir

    with open(os.path.join(expdir, "info.json")) as f:
        exp = json.load(f)["experiment"]

    print(f"Working in experiment: '{exp}'")

    with open(os.path.join(expdir, exp, "info.json")) as f:
        expdata = json.load(f)

    print(
        f"\nExperiment information:\n"
        + f"------------------------\n"
        + f"Name: {expdata['pretty']}\n"
        + f"------------------------\n"
        + f"Datasets:\n"
        + "\n".join(f" - {k:>5s}: {v}" for k, v in expdata["datasets"].items())
    )

    datasets = expdata["datasets"]

    samples = []
    for k in datasets:
        samples.extend(
            [
                [k, id]
                for id in sample_medonc(
                    os.path.join(expdir, exp, "data", k),
                    samples_per_orig if k in expdata["real"] else samples_per,
                )
            ]
        )

    round_data = {"pretty": pretty, "peek": peek, "subjects": samples}

    round_dir = os.path.join(expdir, exp, "rounds")
    round_fn = os.path.join(round_dir, name)
    if os.path.exists(round_fn):
        round_fn_bak = round_fn + ".bak"
        print(f"\nWARNING: round file already exists. Moving it to:\n{round_fn_bak}")
        if os.path.exists(round_fn_bak):
            os.remove(round_fn_bak)
        shutil.move(round_fn, round_fn_bak)

    os.makedirs(round_dir, exist_ok=True)
    with open(round_fn, "w") as f:
        json.dump(round_data, f)

    print(f"\nCreated round:\n{round_fn}")


if __name__ == "__main__":
    main()
