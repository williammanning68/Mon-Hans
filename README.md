# Tasmania Hansard Monitor

Automated tool to download daily transcripts from the Tasmanian Parliament search portal, scan for keywords, and email summaries.

## Configuration
- Add keywords to `keywords.txt`.
- Set SMTP credentials and recipients as environment variables or GitHub Secrets.
- The included GitHub Actions workflow runs daily at 8:30am Hobart time and emails results only when new transcripts are available.

## Running locally
```
pip install -r requirements.txt
python scripts/tas_parl_monitor.py
```

Transcripts are stored under `transcripts/<YYYY-MM-DD>/` and matches are appended to `metadata.csv`.

## Manual testing
Run a local test server and trigger checks for any date and keyword:

```
python scripts/manual_server.py
```

Open `manual_test.html` in a browser, choose a date and keyword, and submit the form to run the monitor and send a test email.
