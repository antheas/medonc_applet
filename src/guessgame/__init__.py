from flask import Flask, render_template
import random

from .ds import generate_patient, load_data

app = Flask(__name__)

dataset = None

def get_relative_fn(fn: str):
    """Returns the directory of a file relative to the script calling this function."""
    import inspect
    import os

    script_fn = inspect.currentframe().f_back.f_globals["__file__"]  # type: ignore
    dirname = os.path.dirname(script_fn)
    return os.path.join(dirname, fn)


@app.route("/")
def index():
    syn = random.randint(0,1) == 1
    patient = f"No patient data (running in fake mode or generation failed)\nSynth: {syn}"
    
    if dataset:
        for _ in range(10):
            try:
                patient = generate_patient(dataset, syn)
                break
            except Exception:
                pass
        
    return render_template("index.html", patient=patient, fake='true' if syn else 'false')


def main():
    import sys

    if (len(sys.argv) < 2):
        print("Missing pasteur dataset path. Enter guessgame <path>")
        sys.exit(1)

    ds_path = sys.argv[1]
    
    if ds_path == "skip":
        print("Skipping dataset loading")
    else:
        global dataset
        print(f"Loading data from:\n{ds_path}")
        dataset = load_data(ds_path)
    
    app.debug = True
    app.run(
        host="127.0.0.1",
        port=6565,
    )


if __name__ == "__main__":
    main()
