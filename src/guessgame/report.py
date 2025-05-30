def get_relative_fn(fn: str):
    import inspect
    import os

    script_fn = inspect.currentframe().f_back.f_globals["__file__"]  # type: ignore
    dirname = os.path.dirname(script_fn)
    return os.path.join(dirname, fn)

_cache_key = None
_cache_img = None

def create_graph(experiment, sessions):
    import io
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import json
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.colors as mcolors
    from collections import defaultdict
    import base64
    import matplotlib.ticker as mtick

    global _cache_key, _cache_img

    data: dict[str, tuple[list[int], list[int]]] = defaultdict(lambda: ([], []))

    # Preprocess data
    for s in sessions.values():
        if s.get("peek", False):
            continue

        for subj, answer in zip(s["subjects"], s["results"]):
            ds = subj[0]
            t = answer["time"]

            if answer["result"] == "correct":
                data[ds][0].append(t)
            else:
                data[ds][1].append(t)

    key = str(dict(data))
    if key == _cache_key:
        print(f"Returning cached result image")
        return _cache_img

    # Dataset names
    datasets = {
        "orig": "Real",
        "e1": "\u03b5 = 1",
        "e10": "\u03b5 = 10",
        "e100": "\u03b5 = 100",
    }

    plt.style.use("default")
    plt.style.use(get_relative_fn("./templates/report.mplstyle"))

    # Plot
    fig, axs = plt.subplots(3, 2, figsize=(7, 6), layout="constrained")

    #
    # Accuracy (per dataset)
    #

    ax = axs[0, 0]
    bar_width = 0.48
    for j in range(2):
        scores = [
            100 * len(data[d][1 - j]) / (len(data[d][0]) + len(data[d][1]))
            for d in datasets
        ]

        ax.bar(
            np.arange(len(datasets)) + j * bar_width,
            scores,
            bar_width,
        )

    ax.set_xticks(np.arange(len(data)) + 0.25)
    ax.set_xticklabels(list(datasets.values()))
    ax.set_ylabel("% Correct")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_title(f"Accuracy (per dataset)")
    ax.legend(["Incorrect", "Correct"], loc="upper right", ncol=3)

    #
    # Time to Guess depending on guess (per dataset)
    #

    ax = axs[0, 1]
    bar_width = 0.48
    for j in range(2):
        scores = [sum(data[d][1 - j]) / len(data[d][1 - j]) for d in datasets]

        ax.bar(
            np.arange(len(datasets)) + j * bar_width,
            scores,
            bar_width,
        )

    ax.set_xticks(np.arange(len(data)) + 0.25)
    ax.set_xticklabels(list(datasets.values()))
    ax.set_ylabel("TTR (s)")
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.1f"))
    ax.set_title(f"Mean Time to Guess (per choice, dataset)")
    ax.legend(["Incorrect", "Correct"], loc="upper left", ncol=3)

    #
    # Precision, Recall (per dataset)
    #

    ax = axs[1, 0]
    bar_width = 0.48

    ax.bar(
        np.arange(len(datasets)),
        [
            (
                100 * len(data[d][0]) / (len(data[d][0]) + len(data["orig"][1]))
                if d != "orig"
                else 100
                * len(data[d][0])
                / (len(data[d][0]) + sum(len(data[v][1]) for v in datasets if v != "orig"))
            )
            for d in datasets
        ],
        bar_width,
        color="#1f6229",
    )
    ax.bar(
        np.arange(len(datasets)) + bar_width,
        [100 * len(data[d][0]) / (len(data[d][0]) + len(data[d][1])) for d in datasets],
        bar_width,
        color="#47c459",
    )

    ax.set_xticks(np.arange(len(data)) + 0.25)
    ax.set_xticklabels(list(datasets.values()))
    ax.set_ylabel("Precision & Recall (%)")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_title(f"Precision & Recall per dataset")
    ax.legend(["Precision", "Recall"], loc="upper right", ncol=3)

    #
    # F1 Score (per dataset)
    #

    ax = axs[1, 1]
    bar_width = 0.9

    precision = np.array(
        [
            (
                len(data[d][0]) / (len(data[d][0]) + len(data["orig"][1]))
                if d != "orig"
                else len(data[d][0])
                / (len(data[d][0]) + sum(len(data[v][1]) for v in datasets if v != "orig"))
            )
            for d in datasets
        ]
    )

    recall = np.array(
        [len(data[d][0]) / (len(data[d][0]) + len(data[d][1])) for d in datasets]
    )

    f1_score = 2 * (precision * recall) / (precision + recall)

    ax.bar(
        np.arange(len(datasets)),
        f1_score,
        bar_width,
        color="#663399",
    )

    ax.set_xticks(np.arange(len(data)) + 0)
    ax.set_xticklabels(list(datasets.values()))
    ax.set_ylabel("F1 Score")
    # ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_title(f"F1 score per dataset")

    #
    # Time Histogram
    #
    ax = axs[2, 0]

    res = np.concatenate([v[0] + v[1] for v in data.values()])
    _, edges = np.histogram(res, bins=8)
    buckets = [(edges[i] + edges[i + 1]) / 2 for i in range(len(edges) - 1)]

    bar_width = 0.22
    cs = list(mcolors.TABLEAU_COLORS.values())
    for i, (name, pretty) in enumerate(datasets.items()):
        hist = np.histogram(data[name][0] + data[name][1], bins=edges)[0]

        # Normalize
        hist = 100 * (hist / np.sum(hist))

        ax.bar(
            np.arange(len(buckets)) + i * bar_width,
            hist,
            bar_width,
            color=cs[i],
        )

    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylabel("Ratio of Answers (%)")
    ax.set_xlabel("Time to Response (s)")
    ax.set_title("Histogram of Time to Response")
    ax.legend(datasets.values(), loc="upper right", ncol=1)

    #
    # Confusion matrix
    #
    ax = axs[2, 1]

    cmat = [[len(data[d][1]), len(data[d][0])] for d in datasets]
    ax.imshow(cmat, interpolation=None, aspect="auto", cmap="cividis", alpha=0.6)
    ax.set_yticks(np.arange(len(data)))
    ax.set_yticklabels(list(datasets.values()))
    ax.set_xticks([0, 1])
    ax.set_title(f"Confusion Matrix")
    ax.set_xticklabels(["Incorrect", "Correct"])
    for (j, i), c in np.ndenumerate(cmat):
        label = f"{c: 3d} ({100 * c / sum(cmat[j]):2.0f}%)"
        ax.text(i, j, label, ha="center", va="center")

        # Prepare ticks
        # ax = axs[-1, 0]
        # ax.set_xticks(np.arange(len(data)) + 0.25)
        # ax.set_xticklabels(list(datasets.values()))
        # ax.set_xlabel("Per Dataset Metrics")
        datasets = {
            "orig": "Real",
            "e1": "\u03b5 = 1",
            "e10": "\u03b5 = 10",
            "e100": "\u03b5 = 100",
        }

    #
    # Convert to base64 jpeg
    #
    my_stringIObytes = io.BytesIO()
    plt.savefig(my_stringIObytes, format="jpg")
    my_stringIObytes.seek(0)
    val = base64.b64encode(my_stringIObytes.read()).decode()

    _cache_key = key
    _cache_img = val

    return val
