import re
import math
import os
import json
from typing import NamedTuple, Any, TypedDict, Callable
import pandas as pd

import logging

FPAT = re.compile(r"{(?P<fun>\w+)\((?P<args>[a-zA-Z0-9\. ,]+)\)}")
ALG = "mare"

logger = logging.getLogger(__name__)


class Round(TypedDict):
    pretty: str
    peek: bool
    subjects: list[tuple[str, str]]


class Experiment(TypedDict):
    pretty: str
    type: str
    dataset_names: dict[str, str]

    datasets: dict[str, Any]
    rounds: dict[str, Round]
    generate: Callable[[dict[str, Any], str, Any], str]


class MedOnc(NamedTuple):
    patients: pd.DataFrame
    lines: pd.DataFrame
    updates: pd.DataFrame
    medicine: pd.DataFrame


class DatasetFunctions(TypedDict):
    load: Callable[[str], Any]
    generate: Callable[[dict[str, Any], str, Any], str]


def generate_patient(ds: dict[str, MedOnc], dataset: str, subject: Any):
    out = ""

    patients, lines, updates, medicine = ds[dataset]

    p = patients[subject]
    weight = None
    bsa = None
    height = None

    out += f"Patient born in {p.birth.year} presents with:\n- {p.primary_icd}: {p.primary_description}, Height: {p.height:.1f}\n"
    if not math.isnan(p.height):
        height = p.height

    plines = lines[lines["id"] == id]
    for i, (lid, l) in enumerate(plines.iterrows()):
        out += f"> L{i+ 1:02d}/{len(plines)}: {l.protocol}\n"

        for j, (uid, u) in enumerate(updates[updates["line_id"] == lid].iterrows()):
            if not math.isnan(u.bsa):
                bsa = u.bsa

            if not math.isnan(u.weight):
                weight = u.weight
                wstr = f" {u.weight:5.1f}kg, {u.bsa:.2f} BSA ({u.weight_date.date()})"
            else:
                wstr = ""
            out += f"  {u.date.date()} C{u.cycle:02d}D{u.day:02d}{wstr}\n"

            for k, (mid, m) in enumerate(
                medicine[medicine["update_id"] == uid].iterrows()
            ):
                # break
                notes = m.notes
                if isinstance(notes, str):
                    match = FPAT.match(notes)
                    if match:
                        pfuns = {
                            "fmgm2": lambda d, acc: (
                                round(d * bsa / acc) * acc if bsa else "INV: no BSA"
                            ),
                            "fmgkg": lambda d, acc: (
                                round(d * weight / acc) * acc
                                if weight
                                else "INV: no weight"
                            ),
                            "fauc": lambda d, acc: "AUC:TODO",
                        }
                        start, end = match.span()
                        fn = match.group("fun")
                        args = eval(match.group("args"))
                        dosage = pfuns[fn](*args) if fn in pfuns else f"UKN:{fn}"
                        notes = f"{notes[:start]}{dosage}{notes[end:]}"

                if str(m.drug) != "nan":
                    out += f"   - {str(m.time.time())[:-3]}: {m.drug:>18s}  {notes}\n"

    return out


def load_medonc_data(ds_path: str):
    return MedOnc(
        pd.read_parquet(os.path.join(ds_path, "patients.pq")),
        pd.read_parquet(os.path.join(ds_path, "lines.pq")),
        pd.read_parquet(os.path.join(ds_path, "updates.pq")),
        pd.read_parquet(os.path.join(ds_path, "medicine.pq")),
    )


dataset_functions: dict[str, DatasetFunctions] = {
    "medonc": {"load": load_medonc_data, "generate": generate_patient},
    "fake": {"load": lambda x: x, "generate": lambda x, y, z: f"{x} {y} {z}"},
}


def load_data(ds_path: str):
    assert os.path.exists(ds_path), f"Path '{ds_path}' does not exist"

    assert os.path.isdir(ds_path), f"Path '{ds_path}' is not a directory"

    data_info = os.path.join(ds_path, "info.json")
    assert os.path.exists(data_info), f"File '{data_info}' does not exist"

    with open(data_info, "r") as f:
        info = json.load(f)

    assert "experiment" in info, f"Key 'experiment' not found in '{data_info}'"

    experiment = info["experiment"]

    experiment_path = os.path.join(ds_path, experiment)
    assert os.path.isdir(experiment_path), f"Path '{experiment}' not found in {ds_path}"

    info_fn = os.path.join(experiment_path, "info.json")
    assert os.path.exists(info_fn), f"File '{info_fn}' does not exist"

    with open(info_fn, "r") as f:
        info = json.load(f)

    pretty = info["pretty"]
    dataset_type = info["type"]
    dataset_names = info["datasets"]

    assert dataset_type in dataset_functions, f"Dataset type '{dataset_type}' not found"
    load_fun = dataset_functions[dataset_type]["load"]

    datasets = {}
    for k in dataset_names:
        ds_path = os.path.join(experiment_path, "data", k)
        assert os.path.exists(ds_path), f"Dataset '{ds_path}' does not exist"

        dataset = load_fun(ds_path)
        datasets[k] = dataset

    round_dir = os.path.join(experiment_path, "rounds")
    assert os.path.exists(round_dir), f"Round directory '{round_dir}' does not exist"

    rounds = {}
    for k in sorted(list(os.listdir(round_dir))):
        rounds[k.replace(".json", "")] = json.load(open(os.path.join(round_dir, k)))

    ds_name_concat = ", ".join([f"'{k}' ({v})" for k, v in dataset_names.items()])
    logger.info(f"Loaded experiment '{pretty}' with datasets '{ds_name_concat}'")
    return Experiment(
        pretty=pretty,
        type=dataset_type,
        dataset_names=dataset_names,
        datasets=datasets,
        rounds=rounds,
        generate=dataset_functions[dataset_type]["generate"],
    )
