# SuPeRR Selector — Pressure Analytics Dashboard

Interactive Streamlit dashboard for IPL/T20 pressure-performance analysis.

## Deploy online (Streamlit Community Cloud)

1. Create a **public GitHub repository** named `SuPeRR-Selector-Dashboard`.
2. Install GitHub Desktop and sign in. Clone the new empty repository to your computer.
3. Copy **all contents** of this folder into the cloned repository. Keep `app.py`, `requirements.txt`, `player_eligibility.csv`, and the `data/` folder at the repository root.
4. Commit the files in GitHub Desktop and click **Push origin**.
5. Open https://share.streamlit.io and sign in using GitHub.
6. Click **Create app** and select your repository, branch `main`, and main file path `app.py`.
7. Click **Deploy**. When deployment finishes, copy the public `https://....streamlit.app` address and submit that link.

The ball-by-ball CSV is larger than GitHub's browser-upload limit, so use GitHub Desktop to commit/push the folder rather than uploading each file through the GitHub website. GitHub's standard per-file limit is 100 MB; the supplied CSV is below that limit.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Files

- `app.py` — Streamlit application
- `requirements.txt` — Python dependencies
- `data/` — supplied competition CSV files
- `player_eligibility.csv` — editable eligibility status table

## Important eligibility note

Historical performance data does not establish current IPL registration or availability. Verify current-season eligibility from official sources before making final selections. The dashboard only excludes players explicitly marked `Retired`, `Ineligible`, or `Unavailable`.
