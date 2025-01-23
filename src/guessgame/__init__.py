from flask import Flask, render_template, request
import random

from .ds import generate_patient, load_data

app = Flask(__name__)

ds_path = None
countdown = 15
ds_names = {}
datasets = {}


def get_relative_fn(fn: str):
    """Returns the directory of a file relative to the script calling this function."""
    import inspect
    import os

    script_fn = inspect.currentframe().f_back.f_globals["__file__"]  # type: ignore
    dirname = os.path.dirname(script_fn)
    return os.path.join(dirname, fn)


@app.route("/")
def index():
    return render_template("index.html", datasets=ds_names)


@app.route("/game")
def game():
    syn = random.randint(0, 1) == 1
    patient = (
        f"No patient data (running in fake mode or generation failed)\nSynth: {syn}"
    )

    dataset = None
    dataset_name = request.args.get("dataset")
    if dataset_name in datasets:
        dataset = datasets[dataset_name]
    elif ds_path and ds_path != "skip":
        dataset = load_data(ds_path, dataset_name)
        datasets[dataset_name] = dataset

    if dataset:
        for _ in range(10):
            try:
                patient = generate_patient(dataset, syn)
                break
            except Exception:
                pass

    return render_template(
        "game.html",
        patient=patient,
        fake="true" if syn else "false",
        countdown=countdown,
    )


@app.route("/results")
def results():
    return render_template("results.html", datasets=ds_names)


def main():
    import sys

    if len(sys.argv) < 3:
        print(
            "Missing pasteur dataset path or datasets. Enter guessgame <path> <datasets>"
        )
        sys.exit(1)

    global ds_path, ds_names, countdown
    ds_path = sys.argv[1]
    ds_names = {}
    for ds in sys.argv[2].split(","):
        k, v = ds.split(":", 1)
        ds_names[k] = v

    if ds_path == "skip":
        print("Skipping dataset loading")

    for arg in sys.argv:
        if arg.startswith("countdown="):
            countdown = int(arg.split("=", 1)[1])

    app.debug = True
    app.run(
        host="127.0.0.1",
        port=6565,
    )


if __name__ == "__main__":
    main()
