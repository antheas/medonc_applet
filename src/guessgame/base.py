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
            if len(v["results"]) < len(v["subjects"]) and not v["finished"]
        },
        history={
            k: f'{v["name"]} at {experiment["rounds"][v["round"]]["pretty"].split(" (", 1)[0]}, score: {len([v for v in v["results"] if v["result"] == "correct"])}/{len(v["results"])}'
            for k, v in sessions.items()
            if (len(v["results"]) == len(v["subjects"]) or v["finished"])
            and len(v["results"]) > 0
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

    session_id = f"{name}_{round}_{datetime.now().strftime('%Y%m%d_%H%M%S')}".lower()

    sessions[session_id] = {
        "version": VERSION,
        "name": name,
        "round": round,
        "subjects": subjects,
        "results": [],
        "finished": False,
    }
    updated.add(session_id)
    save_sessions(experiment, sessions, updated)

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


@app.route("/game", methods=["GET", "POST"])
def game():
    if request.method == "POST":
        # handle Post stuff separately
        data = request.form
        idx = int(data["idx"])
        result = data["result"]
        time = float(data["time"])
        session_id = data["session"]
        session = sessions[session_id]

        if not result:
            logger.warning(f"Empty result for session {session_id}")
        elif idx == len(session["results"]):
            session["results"].append(
                {
                    "result": result,  # type: ignore
                    "time": time,
                }
            )
            updated.add(session_id)
            save_sessions(experiment, sessions, updated)
        else:
            logger.warning(f"Resubmission detected ({idx}) for session {session_id}")
    else:
        session_id = request.args.get("session")
        if session_id not in sessions:
            return redirect("/")

        session = sessions[session_id]

    if len(session["results"]) >= len(session["subjects"]) or session["finished"]:
        return redirect(f"/results?session={session_id}")

    idx = len(session["results"])
    dataset, subject_id = session["subjects"][idx]

    subject = experiment["generate"](experiment["datasets"], dataset, subject_id)

    return render_template(
        "game.html",
        subject=subject,
        session=session_id,
        idx=idx,
        peek="true" if experiment["rounds"][session["round"]]["peek"] else "false",
        score=sum(s["result"] == "correct" for s in session["results"]),
        total=len(session["results"]),
        tries=len(session["subjects"]),
        synth="true" if dataset not in experiment["real"] else "false",
        total_time=int(sum(s["time"] for s in session["results"])),
        name=session["name"],
    )


@app.route("/results")
def results():
    session_id = request.args.get("session")
    if session_id not in sessions:
        return redirect("/")

    session = sessions[session_id]
    if not session["finished"]:
        session["finished"] = True
        updated.add(session_id)
        save_sessions(experiment, sessions, updated)

    results = {
        k: {
            "name": v,
            "correct": 0,
            "incorrect": 0,
        }
        for k, v in experiment["dataset_names"].items()
    }

    score = 0
    total = len(session["results"])

    for i, result in enumerate(session["results"]):
        dataset, _ = session["subjects"][i]
        if result["result"] == "correct":
            results[dataset]["correct"] += 1
            score += 1
        else:
            results[dataset]["incorrect"] += 1

    return render_template(
        "results.html",
        name=session["name"],
        results=results,
        score=score,
        total=total,
        tries=len(session["subjects"]),
        time=int(sum(s["time"] for s in session["results"])),
        round=experiment["rounds"][session["round"]]["pretty"],
    )


def main():
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

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
