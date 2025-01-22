from flask import Flask, render_template

app = Flask(__name__)


def get_relative_fn(fn: str):
    """Returns the directory of a file relative to the script calling this function."""
    import inspect
    import os

    script_fn = inspect.currentframe().f_back.f_globals["__file__"]  # type: ignore
    dirname = os.path.dirname(script_fn)
    return os.path.join(dirname, fn)


@app.route("/")
def index():
    return render_template("index.html", name="test")


def main():
    app.debug = True
    app.run(
        host="127.0.0.1",
        port=6565,
    )


if __name__ == "__main__":
    main()
