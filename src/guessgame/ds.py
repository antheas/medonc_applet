import re
import math
import os
from typing import NamedTuple
import pandas as pd

FPAT = re.compile(r"{(?P<fun>\w+)\((?P<args>[a-zA-Z0-9\. ,]+)\)}")
ALG = "mare"


class MedOnc(NamedTuple):
    patients: pd.DataFrame
    lines: pd.DataFrame
    updates: pd.DataFrame
    medicine: pd.DataFrame


class Datasets(NamedTuple):
    wrk: MedOnc
    syn: MedOnc


def read_data(pq):
    pd.read_parquet(pq)


def load_original_data(ds_path: str):
    return MedOnc(
        pd.read_parquet(ds_path + "/view/medonc/tables/patients.pq"),
        pd.read_parquet(ds_path + "/view/medonc/tables/lines.pq"),
        pd.read_parquet(ds_path + "/view/medonc/tables/updates.pq"),
        pd.read_parquet(ds_path + "/view/medonc/tables/medicine.pq"),
    )


def load_syn_data_latest(ds_path: str):
    ts = sorted(list(os.listdir(ds_path + "/synth/medonc/mare/tables/patients.pq/")))[0]
    print(f"Synthetic Timestamp is {ts}")

    return load_syn_data_ts(ds_path, ts)


def load_syn_data_ts(ds_path: str, ts):
    return MedOnc(
        pd.read_parquet(
            ds_path + "/synth/medonc/mare/tables/patients.pq/" + ts + "/patients.pq"
        ),
        pd.read_parquet(
            ds_path + "/synth/medonc/mare/tables/lines.pq/" + ts + "/lines.pq"
        ),
        pd.read_parquet(
            ds_path + "/synth/medonc/mare/tables/updates.pq/" + ts + "/updates.pq"
        ),
        pd.read_parquet(
            ds_path + "/synth/medonc/mare/tables/medicine.pq/" + ts + "/medicine.pq"
        ),
    )


def load_data(ds_path: str, ts):
    return Datasets(
        load_original_data(ds_path),
        (
            load_syn_data_latest(ds_path)
            if ts is None or ts == "latest"
            else load_syn_data_ts(ds_path, ts)
        ),
    )


def generate_patient(ds: Datasets, syn):
    out = ""

    patients, lines, updates, medicine = ds.syn if syn else ds.wrk

    for id, p in patients.sample(1).iterrows():
        weight = None
        bsa = None
        height = None

        out += f'Patient born in {p.birth.year} presents with:\n- {p.primary_icd}: {p.primary_description}, Height: {p.height:.1f}{" F" if syn else ""}\n'
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
                    wstr = (
                        f" {u.weight:5.1f}kg, {u.bsa:.2f} BSA ({u.weight_date.date()})"
                    )
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
                        out += (
                            f"   - {str(m.time.time())[:-3]}: {m.drug:>18s}  {notes}\n"
                        )

    return out
