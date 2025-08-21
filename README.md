# Tasmania Hansard Monitor

Automated tool to download daily transcripts from the Tasmanian Parliament search portal, scan for keywords, and email summaries.

The scheduled GitHub Action runs every day at **8:30am Hobart time** and sends results to `william.manning@federalgroup.com.au`. An email is only sent when new transcripts contain keyword matches.

## Configuration
- Add keywords to `keywords.txt`.
- Set SMTP credentials as environment variables or GitHub Secrets.

## Running locally
```
pip install -r requirements.txt
python scripts/tas_parl_monitor.py
```

Transcripts are stored under `transcripts/<YYYY-MM-DD>/` and matches are appended to `metadata.csv`.

### Manual testing
Open `manual_run.html` in a browser, select a date, provide a GitHub Personal Access Token with `workflow` scope, and click **Run** to trigger the workflow immediately.
