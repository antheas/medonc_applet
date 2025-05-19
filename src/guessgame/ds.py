import logging.config
import re
import math
import os
import json
from typing import NamedTuple, Any, TypedDict, Callable, Literal, cast
import pandas as pd
import numpy as np
import time

import logging

VERSION = 1
FPAT = re.compile(r"{(?P<fun>\w+)\((?P<args>[a-zA-Z0-9\. ,]+)\)}")
ALG = "mare"

logger = logging.getLogger(__name__)


class Round(TypedDict):
    pretty: str
    peek: bool
    subjects: list[tuple[str, str]]


class Result(TypedDict):
    time: float
    result: Literal["correct", "incorrect", "timeout", "skip"]


class Session(TypedDict):
    version: int
    name: str
    round: str
    subjects: list[tuple[str, str]]
    results: list[Result]
    finished: bool


class DatasetFunctions(TypedDict):
    load: Callable[[str], Any]
    generate: Callable[[dict[str, Any], str, Any], str]
    sample: Callable[[dict[str, Any], str, int], None]


class Experiment(TypedDict):
    pretty: str
    type: str
    dataset_names: dict[str, str]
    session_path: str
    real: list[str]

    datasets: dict[str, Any]
    rounds: dict[str, Round]
    generate: Callable[[dict[str, Any], str, Any], str]
    funs: DatasetFunctions


class MedOnc(NamedTuple):
    patients: pd.DataFrame
    lines: pd.DataFrame
    updates: pd.DataFrame
    medicine: pd.DataFrame


def generate_patient_v2(ds: dict[str, MedOnc], dataset: str, subject: Any):
    from flask import render_template

    patients, lines, updates, medicine = ds[dataset]

    p = patients.loc[subject]
    weight = None
    bsa = None

    demo = {
        "icd": p.primary_icd if not pd.isna(p.primary_icd) else "-",
        "icd_desc": (
            p.primary_description if not pd.isna(p.primary_description) else "-"
        ),
        "height": f"{p.height/100:.2f}m" if not pd.isna(p.height) else "-",
        "bsa": "-",
        "weight": "-",
        "weight_date": None,
        "age": None,
        "age_last_visit": None,
        "birth": p.birth.strftime(f"%d/%m/%Y"),
        "death": "-",
        "last_visit": "-",
    }

    treat = []
    treat_date = None

    plines = lines[lines["id"] == subject]

    # Prefill data to avoid invalids
    for i, (lid, l) in enumerate(plines.iterrows()):
        for j, (uid, u) in enumerate(updates[updates["line_id"] == lid].iterrows()):
            if not demo["age"]:
                try:
                    demo["age"] = f"{(u.date - p.birth).days / 365:.0f} years"
                except Exception:
                    pass

            if hasattr(u, "bsa") and not math.isnan(u.bsa) and demo["bsa"] == "-":
                demo["bsa"] = f"{u.bsa:.2f}"
                bsa = u.bsa

            if hasattr(u, "weight") and not math.isnan(u.weight) and demo["weight"] == "-":
                weight = u.weight
                demo["weight"] = f"{u.weight:.1f}kg"

            if (
                hasattr(u, "weight_date")
                and not demo["weight_date"]
                and u.weight_date
                and not pd.isna(u.weight_date)
            ):
                demo["weight_date"] = u.weight_date.strftime(f"%d/%m/%Y")

    for i, (lid, l) in enumerate(plines.iterrows()):
        rows = list(updates[updates["line_id"] == lid].iterrows())
        if not len(rows):
            continue

        # treat.append(
        #     {
        #         "type": "line",
        #         "protocol": l.protocol,
        #     },
        # )
        for j, (uid, u) in enumerate(rows):
            has_cycle = False

            if not demo["age"]:
                try:
                    demo["age"] = f"{(u.date - p.birth).days / 365:.0f}"
                except Exception:
                    pass

            if hasattr(u, "bsa") and not math.isnan(u.bsa) and not demo["bsa"]:
                demo["bsa"] = f"{u.bsa:.2f}"
                bsa = bsa

            if hasattr(u, "weight") and not math.isnan(u.weight) and not demo["weight"]:
                weight = weight
                demo["weight"] = f"{u.weight:.1}kg"

            if (
                not demo["weight_date"]
                and hasattr(u, "weight_date")
                and u.weight_date
                and not pd.isna(u.weight_date)
            ):
                demo["weight_date"] = u.weight_date.strftime(f"%d/%m/%Y")

            for k, (mid, m) in enumerate(
                medicine[medicine["update_id"] == uid].iterrows()
            ):
                # break
                notes = m.notes
                write = str(m.drug) != "nan"
                if isinstance(notes, str):
                    match = FPAT.search(notes)
                    if match:
                        pfuns = {
                            "fmgm2": lambda d, acc: ((d * bsa) // 1 if bsa else None),
                            "fmgkg": lambda d, acc: (
                                (d * weight) // 1 if weight else None
                            ),
                            "fauc": lambda d, acc: ((d * 1.2) // 1 * 100), # GFR of 95+round a bit
                            "rmgm2": lambda d, acc: (d // bsa if bsa else None),
                        }
                        start, end = match.span()
                        fn = match.group("fun")
                        args = eval(match.group("args"))
                        if fn in pfuns:
                            dosage = pfuns[fn](*args)
                        else:
                            print(f"Function {fn}" not in pfuns)
                            dosage = None

                        if dosage is not None:
                            notes = f"{notes[:start]}{int(dosage)}{notes[end:]}"
                        else:
                            print(f"Dosage of {notes} is none", weight, bsa)
                        # else:
                        #     write = False

                if write:
                    treat.append(
                        {
                            "type": "med",
                            "date": u.date.strftime(f"%d/%m/%Y"),
                            "time": m.time.strftime(f"%H:%M"),
                            "drug": m.drug,
                            # "cycle": f"C{u.cycle:02d}D{u.day:02d}",
                            "notes": notes,
                            # "protocol": l.protocol,
                        }
                    )
                    has_cycle = True
                    if u.date is not None:
                        treat_date = u.date

            if has_cycle:
                treat.append({"type": "cycle"})

    # Remove last treatment line for evenness
    if treat and treat[-1] and treat[-1].get("type", None) == "cycle":
        del treat[-1]

    if treat_date is not None:
        if not pd.isna(p["months_to_death"]) and p["months_to_death"] > 0:
            ddate = treat_date + pd.Timedelta(abs(p["months_to_death"]) * 30, "day")

            # Doctors know the dataset ends in 2022, so prevent showing them
            # death dates in years afterwards
            if ddate.year >= 2022:
                ddate = pd.Timestamp(
                    year=2021,
                    month=ddate.month,
                    day=ddate.day
                )

            demo["death"] = ddate.strftime(f"%d/%m/%Y")
            demo["age_death"] = f"{(ddate - p.birth).days / 365:.0f} years"

        ddate = treat_date
        demo["last_visit"] = ddate.strftime(f"%d/%m/%Y")
        demo["age_last_visit"] = f"{(ddate - p.birth).days / 365:.0f} years"

    return render_template(
        "patient.html",
        demo=demo,
        treat=treat,
    )


def generate_patient(ds: dict[str, MedOnc], dataset: str, subject: Any):
    out = ""

    patients, lines, updates, medicine = ds[dataset]

    p = patients.loc[subject]
    weight = None
    bsa = None
    height = None

    out += f"Patient born in {p.birth.year} presents with:\n- {p.primary_icd}: {p.primary_description}, Height: {p.height:.1f}\n"
    if not math.isnan(p.height):
        height = p.height

    plines = lines[lines["id"] == subject]
    for i, (lid, l) in enumerate(plines.iterrows()):
        out += f"> L{i+ 1:02d}/{len(plines)}: {l.protocol}\n"

        for j, (uid, u) in enumerate(updates[updates["line_id"] == lid].iterrows()):
            if hasattr(u, "bsa") and not math.isnan(u.bsa):
                bsa = u.bsa

            if hasattr(u, "bsa") and not math.isnan(u.weight):
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
                            "fauc": lambda d, acc: round(84 * d / acc) * acc,
                        }
                        start, end = match.span()
                        fn = match.group("fun")
                        args = eval(match.group("args"))
                        dosage = pfuns[fn](*args) if fn in pfuns else f"UKN:{fn}"
                        notes = f"{notes[:start]}{dosage}{notes[end:]}"

                if str(m.drug) != "nan":
                    out += f"   - {str(m.time.time())[:-3]}: {m.drug:>18s}  {notes}\n"

    return out


def sample_patients(ds: dict[str, MedOnc], dataset: str, num: int):
    import numpy as np

    for idx in np.random.choice(ds[dataset].patients.index.unique(), num):
        print(f'["{dataset}", {idx}],')


def load_medonc_data(ds_path: str):
    return MedOnc(
        pd.read_parquet(os.path.join(ds_path, "patients.pq")),
        pd.read_parquet(os.path.join(ds_path, "lines.pq")),
        pd.read_parquet(os.path.join(ds_path, "updates.pq")),
        pd.read_parquet(os.path.join(ds_path, "medicine.pq")),
    )


dataset_functions: dict[str, DatasetFunctions] = {
    "medonc": {
        "load": load_medonc_data,
        "generate": generate_patient_v2,
        "sample": sample_patients,
    },
    "fake": {
        "load": lambda x: x,
        "generate": lambda x, y, z: f"{y} {z}",
        "sample": lambda x, y, z: None,
    },
}


def load_data(ds_path: str, ds_filter: list[str] | None = None):
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
        if ds_filter and k not in ds_filter:
            continue

        if k.startswith("_"):
            # Allow disabling datasets with _ prefix (no JSON comments)
            continue

        logger.info(f"Loading dataset '{k}'")
        start = time.perf_counter()
        ds_path = os.path.join(experiment_path, "data", k)
        assert os.path.exists(ds_path), f"Dataset '{ds_path}' does not exist"

        dataset = load_fun(ds_path)
        datasets[k] = dataset

        logger.info(f"Loaded dataset '{k}' in {time.perf_counter()-start:.1f}s")

    round_dir = os.path.join(experiment_path, "rounds")
    assert os.path.exists(round_dir), f"Round directory '{round_dir}' does not exist"

    rounds = {}
    for k in sorted(list(os.listdir(round_dir))):
        if not k.endswith(".json"):
            continue
        try:
            rounds[k.replace(".json", "")] = json.load(open(os.path.join(round_dir, k)))
        except Exception:
            logger.exception(f"Round '{k}' file is corrupted")

    ds_name_concat = ", ".join([f"'{k}' ({v})" for k, v in dataset_names.items()])
    logger.info(f"Loaded experiment '{pretty}' with datasets {ds_name_concat}")

    funs = dataset_functions[dataset_type]

    return Experiment(
        pretty=pretty,
        type=dataset_type,
        real=info["real"],
        dataset_names=dataset_names,
        datasets=datasets,
        rounds=rounds,
        generate=funs["generate"],
        session_path=os.path.join(experiment_path, "results"),
        funs=funs,
    )


def load_sessions(exp: Experiment):
    if not os.path.exists(exp["session_path"]):
        return {}

    sessions = {}
    for fn in os.listdir(exp["session_path"]):
        if not fn.endswith(".json"):
            continue

        with open(os.path.join(exp["session_path"], fn), "r") as f:
            session = cast(Session, json.load(f))
            if session["version"] != VERSION:
                logger.warning(
                    f"Session '{fn}' has version {session['version']} instead of {VERSION}"
                )
                continue
            sessions[fn.replace(".json", "")] = session

    return sessions


def save_sessions(exp: Experiment, sessions: dict[str, Session], updated: set[str]):
    if not os.path.exists(exp["session_path"]):
        os.makedirs(exp["session_path"])

    for k in list(updated):
        try:
            with open(os.path.join(exp["session_path"], f"{k}.json"), "w") as f:
                json.dump(sessions[k], f, indent=2)
            updated.remove(k)
        except Exception as e:
            logger.error(f"Error saving session '{k}': {e}")


def delete_session(exp: Experiment, session_id: str):
    if not os.path.exists(exp["session_path"]):
        return

    session_fn = os.path.join(exp["session_path"], f"{session_id}.json")
    if os.path.exists(session_fn):
        os.remove(session_fn)
    else:
        logger.warning(f"Session '{session_id}' not found")


if __name__ == "__main__":
    import sys

    logging.basicConfig()

    if len(sys.argv) < 4:
        # E.g., python -m guessgame.ds ./experiments orig 25 | tee scratch.txt
        print(f"Syntax: {sys.argv[0]} <data> <dataset> <samples>")
        sys.exit(1)

    exp = load_data(sys.argv[1], [sys.argv[2]])
    exp["funs"]["sample"](exp["datasets"], sys.argv[2], int(sys.argv[3]))
