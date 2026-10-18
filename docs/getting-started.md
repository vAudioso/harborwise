# Getting started

This guide assumes no experience with GitHub or Python projects. It takes about 10 minutes.

## What you need

- **Python 3.11 or newer.** Check by running `python3 --version` in a terminal. If it isn't installed, get it from [python.org/downloads](https://www.python.org/downloads/).
- **Git**, to download the project. On macOS it's already there. On Windows, install [Git for Windows](https://git-scm.com/download/win).
- **macOS only:** XGBoost needs OpenMP. Install [Homebrew](https://brew.sh), then run `brew install libomp`.
- **Optional:** [VS Code](https://code.visualstudio.com/) to browse and run the project.

## 1. Download the project

Open a terminal (on macOS: the Terminal app; on Windows: Git Bash) and run:

```bash
git clone https://github.com/vAudioso/harborwise.git
cd harborwise
```

No Git? On the [project page](https://github.com/vAudioso/harborwise), click the green **Code** button, then **Download ZIP**, and unzip it.

## 2. Set everything up and open the website

```bash
make quickstart
```

This one command:

1. creates a private Python environment in `.venv/` and installs the libraries (a few minutes, once)
2. downloads the 2019 ship-tracking dataset from Zenodo (67 MB)
3. downloads the already-trained models (140 MB), so you don't have to train them
4. starts the server and opens **http://localhost:8000/app/** in your browser

When the website opens, the badge at the top should read **"LIVE · HARBORWISE API"**. Press `Ctrl+C` in the terminal to stop the server.

Next time, you only need:

```bash
make app
```

## Without `make` (Windows, or if `make` isn't available)

Run these one at a time:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
python scripts/download_data.py
python scripts/download_models.py
.venv\Scripts\python -m uvicorn api.main:app
```

Then open http://localhost:8000/app/ yourself. On macOS or Linux, use `.venv/bin/python` instead of `.venv\Scripts\python`.

## In VS Code

1. **File → Open Folder…** and choose the `harborwise` folder. Accept the recommended extensions when asked.
2. Do steps 1–3 of `make quickstart` once, in **Terminal → New Terminal**: `make setup download-data download-models`.
3. Open **Run and Debug** (`Cmd+Shift+D` / `Ctrl+Shift+D`), pick **"API: run HarborWise"**, and press ▶. The website opens automatically.
4. To run the tests, open the **Testing** panel (flask icon) and press ▶.

## Useful commands

Run `make help` to see them all.

| Command | What it does |
|---|---|
| `make app` | Start the server and open the website |
| `make test` | Run the tests |
| `make pipeline` | Retrain everything from the raw data (about 25 minutes) |
| `make quick` | A faster, rougher retrain (about 5 minutes) for checking changes |
| `make clean` | Delete generated models and data (keeps the code and raw CSVs) |

## Troubleshooting

| Problem | Fix |
|---|---|
| `Address already in use` | The server is already running in another terminal. Close it, or just open http://localhost:8000/app/. |
| Website badge says **OFFLINE SAMPLE** | The site can't reach the server. Check the terminal shows `Uvicorn running on…`, then refresh the page. |
| `XGBoost Library (libxgboost.dylib) could not be loaded` | macOS needs OpenMP: `brew install libomp`. |
| `CERTIFICATE_VERIFY_FAILED` | The download scripts fall back to `curl` automatically. If that fails too, run `/Applications/Python*/Install\ Certificates.command`. |
| `make: command not found` | Use the commands under "Without `make`" above. |
| Something else | [Open an issue](https://github.com/vAudioso/harborwise/issues/new/choose) and paste the error message. |
