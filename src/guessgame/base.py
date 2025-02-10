from flask import Flask, render_template, request, redirect
import random
import logging
from datetime import datetime
from typing import cast
from .ds import (
    generate_patient,
    load_sessions,
    save_sessions,
    delete_session,
    load_data,
    Experiment,
    Session,
    VERSION,
)

app = Flask(__name__)


logger = logging.getLogger(__name__)

experiment: Experiment = cast(Experiment, None)
sessions: dict[str, Session] = {}
updated: set[str] = set()


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
        "index.html",
        rounds={k: v["pretty"] for k, v in experiment["rounds"].items()},
        sessions={
            k: f'{v["name"]}, {experiment["rounds"][v["round"]]["pretty"].split(" (", 1)[0]} ({len(v["results"])}/{len(v["subjects"])})'
            for k, v in sessions.items()
            if len(v["results"]) < len(v["subjects"])
        },
    )


@app.route("/begin")
def start():
    name = request.args.get("name")
    round = request.args.get("round")
    assert round is not None and name is not None

    # only keep a-z A-Z 0-9 and _ from name
    name = "".join([c for c in name if c.isalnum() or c == "_"])

    subjects = experiment["rounds"][round]["subjects"]
    random.shuffle(subjects)

    session_id = f"{name}_{round}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    sessions[session_id] = {
        "version": VERSION,
        "name": name,
        "round": round,
        "subjects": subjects,
        "results": [],
    }
    return redirect(f"/game?session={session_id}")


@app.route("/delete")
def delete():
    session = request.args.get("session")
    assert session is not None

    if session in sessions:
        del sessions[session]
    if session in updated:
        updated.remove(session)

    # Sanitive name!!!
    session = session.replace("/", "").replace("\\", "")
    delete_session(experiment, session)

    return redirect("/")


@app.route("/game")
def game():
    session_id = request.args.get("session")
    if session_id not in sessions:
        return redirect("/")

    session = sessions[session_id]

    if request.method == "POST":
        data = request.form
        idx = int(data["idx"])
        result = data["result"]
        time = float(data["time"])

        if idx <= len(session["results"]):
            session["results"].append(
                {
                    "result": result,  # type: ignore
                    "time": time,
                }
            )
        else:
            logger.warning(f"Resubmission detected ({idx}) for session {session_id}")

    idx = len(session["results"])
    dataset, subject = session["subjects"][idx]

    patient = experiment['generate'](experiment["datasets"], dataset, subject)

    return render_template(
        "game.html",
        patient=patient,
        idx=idx,
        peak=experiment["rounds"][session["round"]]["peek"],
        session_id=session_id,
        synth=dataset not in experiment["real"],
        name=session["name"],
    )


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

    global experiment, sessions
    try:
        experiment = load_data(ds_path)
        sessions = load_sessions(experiment)
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
