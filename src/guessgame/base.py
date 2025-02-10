from flask import Flask, render_template, request
import random
import logging
from typing import cast
from .ds import generate_patient, load_data, Experiment

app = Flask(__name__)

logger = logging.getLogger(__name__)

experiment: Experiment = cast(Experiment, None)
sessions = []


def get_relative_fn(fn: str):
    """Returns the directory of a file relative to the script calling this function."""
    import inspect
    import os

    script_fn = inspect.currentframe().f_back.f_globals["__file__"]  # type: ignore
    dirname = os.path.dirname(script_fn)
    return os.path.join(dirname, fn)


@app.route("/")
def index():
    return render_template(
        "index.html", rounds={k: v["pretty"] for k, v in experiment["rounds"].items()}
    )


# @app.route("/game")
# def game():
#     syn = random.randint(0, 1) == 1
#     patient = (
#         f"No patient data (running in fake mode or generation failed)\nSynth: {syn}"
#     )

#     dataset = None
#     dataset_name = request.args.get("dataset")
#     if dataset_name in datasets:
#         dataset = datasets[dataset_name]
#     elif ds_path and ds_path != "skip":
#         dataset = load_data(ds_path, dataset_name)
#         datasets[dataset_name] = dataset

#     if dataset:
#         for _ in range(10):
#             try:
#                 patient = generate_patient(dataset, syn)
#                 break
#             except Exception:
#                 pass

#     return render_template(
#         "game.html",
#         patient=patient,
#         fake="true" if syn else "false",
#         countdown=countdown,
#     )


# @app.route("/results")
# def results():
#     return render_template("results.html", datasets=datasets)


def main():
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

    if len(sys.argv) < 2:
        print("Missing dataset path. Enter guessgame <path> [args]")
        sys.exit(1)

    ds_path = sys.argv[1]

    global experiment
    try:
        experiment = load_data(ds_path)
    except AssertionError as e:
        logger.error(e)
        return

    if "--browser" in sys.argv:
        import webbrowser

        # We are deploying, reloads will reopen the browser
        app.debug = False
        webbrowser.open("http://localhost:6565/")
    else:
        app.debug = True

    app.run(
        host="127.0.0.1",
        port=6565,
    )
