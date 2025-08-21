import csv
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import nltk

WAIT_SECS = 25
CLICK_DELAY = 0.6
NAV_DELAY = 0.4


def build_daily_url(d: date) -> str:
    return (
        "https://search.parliament.tas.gov.au/search/isysquery/"
        "8e715d42-5fe7-4c4b-a8b5-8c1dbdd29c36/"
        f"{d:%Y %m %d}-{d:%Y %m %d}/filter/date/"
    )


def make_driver(download_dir: Path):
    opts = ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    prefs = {
        "download.default_directory": str(download_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    opts.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=opts)


def wait_downloads_clear(directory: Path):
    deadline = time.time() + 180
    while time.time() < deadline:
        if not any(f.name.endswith(".crdownload") for f in directory.iterdir()):
            return
        time.sleep(0.5)


def dismiss_banners(driver):
    for xp in [
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'agree')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'got it')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ok')]",
        "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
        "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'agree')]",
        "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'got it')]",
        "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ok')]",
    ]:
        try:
            WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            ).click()
            time.sleep(0.2)
        except Exception:
            pass


def click_first_viewer_title(driver) -> bool:
    wait = WebDriverWait(driver, WAIT_SECS)
    try:
        a = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@onclick,'isys.viewer.show')]")
            )
        )
        a.click()
        return True
    except Exception:
        return False


def parse_toolbar_counts(text: str):
    m = re.search(r"\[\s*(\d+)\s+of\s+(\d+)\s*\]", text, flags=re.I)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def ensure_first_doc(driver, total: int):
    wait = WebDriverWait(driver, WAIT_SECS)
    prev_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#viewer_toolbar .btn.btn-prev"))
    )
    for _ in range(total + 2):
        t = wait.until(
            EC.visibility_of_element_located((By.ID, "viewer_toolbar_filename"))
        ).text
        cur, tot = parse_toolbar_counts(t)
        if tot == total and cur == 1:
            return
        prev_btn.click()
        time.sleep(NAV_DELAY)


def click_download_as_text(driver):
    wait = WebDriverWait(driver, WAIT_SECS)
    dl_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#viewer_toolbar .btn.btn-download"))
    )
    dl_btn.click()
    time.sleep(0.2)
    as_text = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//ol[@id='viewer_toolbar_download']//li[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'as text')]",
            )
        )
    )
    as_text.click()


def click_next(driver):
    wait = WebDriverWait(driver, WAIT_SECS)
    nxt = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#viewer_toolbar .btn.btn-next"))
    )
    nxt.click()


def iterate_and_download(driver, directory: Path):
    wait = WebDriverWait(driver, WAIT_SECS)
    title_el = wait.until(
        EC.visibility_of_element_located((By.ID, "viewer_toolbar_filename"))
    )
    cur, total = parse_toolbar_counts(title_el.text)
    if not total:
        print("  [error] Could not read total doc count from toolbar.")
        return
    ensure_first_doc(driver, total)
    for i in range(1, total + 1):
        click_download_as_text(driver)
        time.sleep(CLICK_DELAY)
        wait_downloads_clear(directory)
        if i < total:
            click_next(driver)
            target = f"[{i+1} of {total}]"
            WebDriverWait(driver, WAIT_SECS).until(
                EC.text_to_be_present_in_element((By.ID, "viewer_toolbar_filename"), target)
            )
            time.sleep(NAV_DELAY)


def run_download(directory: Path, d: date):
    url = build_daily_url(d)
    driver = make_driver(directory)
    try:
        driver.get(url)
        dismiss_banners(driver)
        if not click_first_viewer_title(driver):
            print("[error] Could not open viewer")
            return
        WebDriverWait(driver, WAIT_SECS).until(
            EC.visibility_of_element_located((By.ID, "viewer_toolbar"))
        )
        dismiss_banners(driver)
        iterate_and_download(driver, directory)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def load_keywords(path: Path) -> List[str]:
    if not path.exists():
        return []
    return [k.strip() for k in path.read_text(encoding="utf-8").splitlines() if k.strip()]


def find_speaker(lines: List[str], idx: int) -> str:
    for j in range(idx, -1, -1):
        m = re.match(r"^([A-Z][A-Za-z .'\-]+)\s-", lines[j])
        if m:
            return m.group(1)
    return "Unknown"


def extract_mentions(file_path: Path, keywords: List[str]) -> List[Dict[str, str]]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    mentions = []
    for idx, line in enumerate(lines):
        for kw in keywords:
            if kw.lower() in line.lower():
                start = max(idx - 2, 0)
                end = min(idx + 3, len(lines))
                quote = " ".join(l.strip() for l in lines[start:end])
                speaker = find_speaker(lines, idx)
                mentions.append(
                    {
                        "file": file_path.name,
                        "keyword": kw,
                        "quote": quote,
                        "speaker": speaker,
                    }
                )
    return mentions


def save_metadata(matches: List[Dict[str, str]], date_str: str, path: Path):
    if not matches:
        return
    fieldnames = ["date", "file", "speaker", "keyword", "quote"]
    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for m in matches:
            writer.writerow(
                {
                    "date": date_str,
                    **m,
                }
            )


def send_email(matches: List[Dict[str, str]], date_str: str, recipients: Optional[str] = None):
    import smtplib
    from email.message import EmailMessage

    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    if recipients is None:
        recipients = os.environ.get("RECIPIENTS", "william.manning@federalgroup.com.au")
    if not smtp_user or not smtp_pass or not recipients:
        print("[warn] Email credentials not provided; skipping email")
        return
    body_lines: List[str] = []
    if matches:
        for m in matches:
            body_lines.append(
                f"Keyword: {m['keyword']}\nSpeaker: {m['speaker']}\nQuote: {m['quote']}\nFile: {m['file']}\n"
            )
    else:
        body_lines.append(f"No keyword matches found in transcripts for {date_str}.")
    msg = EmailMessage()
    msg["Subject"] = f"Tasmania Hansard matches for {date_str}"
    msg["From"] = smtp_user
    msg["To"] = recipients.split(",")
    msg.set_content("\n\n".join(body_lines))

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port) as s:
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)


def run_monitor(target_date: date, keywords: List[str], recipients: Optional[str] = None) -> bool:
    """Run download, scan for keywords and send email.

    Returns True if transcripts were downloaded, False otherwise.
    """
    date_str = target_date.isoformat()
    download_dir = Path("transcripts") / date_str
    download_dir.mkdir(parents=True, exist_ok=True)
    run_download(download_dir, target_date)
    transcripts = list(download_dir.glob("*.txt"))
    if not transcripts:
        print("[info] No new documents for this date; skipping email.")
        return False

    all_matches: List[Dict[str, str]] = []
    for txt in transcripts:
        all_matches.extend(extract_mentions(txt, keywords))

    save_metadata(all_matches, date_str, Path("metadata.csv"))
    send_email(all_matches, date_str, recipients)
    return True


def main():
    keywords = load_keywords(Path("keywords.txt"))
    run_monitor(date.today(), keywords)


if __name__ == "__main__":
    nltk.download('punkt', quiet=True)
    main()
