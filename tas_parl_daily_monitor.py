import os, re, time, datetime, logging
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# Configuration
DOWNLOAD_DIR = "./Transcripts"
WAIT_SECS = 25
CLICK_DELAY = 0.6
NAV_DELAY = 0.4

def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('parliament_monitor.log'),
            logging.StreamHandler()
        ]
    )

def make_driver():
    """Create and configure the Edge WebDriver"""
    opts = EdgeOptions()
    opts.add_argument("--start-maximized")
    # Uncomment for headless operation
    # opts.add_argument("--headless=new")
    
    prefs = {
        "download.default_directory": os.path.abspath(DOWNLOAD_DIR),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    opts.add_experimental_option("prefs", prefs)
    return webdriver.Edge(options=opts)

def wait_downloads_clear():
    """Wait until any Edge temp downloads (.crdownload) are gone"""
    deadline = time.time() + 180
    while time.time() < deadline:
        if not any(f.lower().endswith(".crdownload") for f in os.listdir(DOWNLOAD_DIR)):
            return
        time.sleep(0.5)

def dismiss_banners(driver):
    """Best-effort to close cookie/consent banners that may block the toolbar"""
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
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp))).click()
            time.sleep(0.2)
        except Exception:
            pass

def get_search_query_for_date(target_date=None):
    """
    Generate the exact search query for a specific date
    Format: "House of Assembly Tuesday 17 March 2020" or "Legislative Council Tuesday 17 March 2020"
    """
    if target_date is None:
        target_date = datetime.date.today()
    
    # Format: "Tuesday 17 March 2020"
    day_name = target_date.strftime("%A")
    day = target_date.strftime("%d").lstrip('0')
    month_name = target_date.strftime("%B")
    year = target_date.strftime("%Y")
    
    # Search for documents with this date pattern
    query = f'"{day_name} {day} {month_name} {year}"'
    return query

def search_for_documents(driver, query):
    """Navigate to search page and execute search for specific date"""
    logging.info(f"Searching for documents with query: {query}")
    
    # Go to main search page
    driver.get("https://search.parliament.tas.gov.au/search/")
    time.sleep(2)
    dismiss_banners(driver)
    
    # Wait for search input and enter query
    try:
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "IW_FIELD_WEB_STYLE"))
        )
        
        # Clear and enter search query
        search_input.clear()
        search_input.send_keys(query)
        search_input.send_keys(Keys.RETURN)
        
        # Wait for results to load
        time.sleep(3)
        dismiss_banners(driver)
        
        return True
    except Exception as e:
        logging.error(f"Error during search: {e}")
        return False

def get_document_links(driver):
    """Extract all document links from search results"""
    links = []
    try:
        # Wait for results to appear
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".result-title a"))
        )
        
        result_elements = driver.find_elements(By.CSS_SELECTOR, ".result-title a")
        for element in result_elements:
            # Check if it's a viewer link
            onclick = element.get_attribute("onclick") or ""
            if "isys.viewer.show" in onclick:
                links.append({
                    'element': element,
                    'text': element.text,
                    'onclick': onclick
                })
        logging.info(f"Found {len(links)} document links")
        return links
    except Exception as e:
        logging.error(f"Error extracting document links: {e}")
        return []

def click_first_viewer_title(driver) -> bool:
    """
    On the results list, click the first anchor whose onclick contains isys.viewer.show(...).
    This reliably opens the viewer for document 1 in the set.
    """
    wait = WebDriverWait(driver, WAIT_SECS)
    try:
        a = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(@onclick,'isys.viewer.show')]")
        ))
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
    """
    If the viewer didn't open at [1 of total], click Prev until it does.
    """
    wait = WebDriverWait(driver, WAIT_SECS)
    prev_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#viewer_toolbar .btn.btn-prev")))
    for _ in range(total + 2):
        t = wait.until(EC.visibility_of_element_located((By.ID, "viewer_toolbar_filename"))).text
        cur, tot = parse_toolbar_counts(t)
        if tot == total and cur == 1:
            return
        prev_btn.click()
        time.sleep(NAV_DELAY)

def click_download_as_text(driver):
    wait = WebDriverWait(driver, WAIT_SECS)
    dl_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#viewer_toolbar .btn.btn-download")))
    dl_btn.click()
    time.sleep(0.2)
    as_text = wait.until(EC.element_to_be_clickable((
        By.XPATH,
        "//ol[@id='viewer_toolbar_download']//li[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'as text')]"
    )))
    as_text.click()

def click_next(driver):
    wait = WebDriverWait(driver, WAIT_SECS)
    nxt = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#viewer_toolbar .btn.btn-next")))
    nxt.click()

def is_already_downloaded(filename):
    """Check if file already exists to avoid duplicates"""
    return os.path.exists(os.path.join(DOWNLOAD_DIR, filename))

def rename_downloaded_file(desired_filename):
    """Try to rename the most recently downloaded file"""
    try:
        # Get list of files in download directory
        files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
        
        # Find the most recently modified file (likely the one just downloaded)
        if files:
            latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(DOWNLOAD_DIR, f)))
            
            # Rename it to the desired filename
            if not latest_file.endswith('.crdownload'):  # Make sure it's not still downloading
                os.rename(
                    os.path.join(DOWNLOAD_DIR, latest_file),
                    os.path.join(DOWNLOAD_DIR, desired_filename)
                )
                logging.info(f"Renamed {latest_file} to {desired_filename}")
    except Exception as e:
        logging.error(f"Error renaming file: {e}")

def process_document_in_viewer(driver):
    """Process the current document in the viewer"""
    wait = WebDriverWait(driver, WAIT_SECS)
    title_el = wait.until(EC.visibility_of_element_located((By.ID, "viewer_toolbar_filename")))
    
    # Extract proper filename from title
    document_title = title_el.text.split('[')[0].strip()  # Remove "[X of Y]" part
    safe_filename = re.sub(r'[^\w\s-]', '', document_title).strip().replace(' ', '_')
    filename = f"{safe_filename}.txt"
    
    # Check if already downloaded
    if is_already_downloaded(filename):
        logging.info(f"Document already downloaded: {filename}")
        return
    
    # Download the document
    click_download_as_text(driver)
    time.sleep(CLICK_DELAY)
    wait_downloads_clear()
    
    # Rename the downloaded file
    rename_downloaded_file(filename)

def close_viewer(driver):
    """Close the viewer and return to search results"""
    try:
        # Try to find a close button
        close_buttons = driver.find_elements(By.CSS_SELECTOR, ".viewer-close-button, .close-button, [title='Close']")
        if close_buttons:
            close_buttons[0].click()
        else:
            # Fallback: navigate back
            driver.back()
        time.sleep(2)
    except Exception as e:
        logging.error(f"Error closing viewer: {e}")
        driver.back()
        time.sleep(2)

def main():
    """Main function to run the monitoring process"""
    setup_logging()
    logging.info("Starting Tasmania Parliament Transcript Monitor")
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    driver = make_driver()
    
    try:
        # Get today's search query
        search_query = get_search_query_for_date()
        
        # Execute search
        if search_for_documents(driver, search_query):
            # Get document links
            document_links = get_document_links(driver)
            
            if document_links:
                logging.info(f"Found {len(document_links)} documents for today")
                
                # Process each document
                for i, link_info in enumerate(document_links):
                    logging.info(f"Processing document {i+1}: {link_info['text']}")
                    
                    # Click the document link
                    try:
                        link_info['element'].click()
                        
                        # Wait for viewer to load
                        WebDriverWait(driver, WAIT_SECS).until(
                            EC.visibility_of_element_located((By.ID, "viewer_toolbar"))
                        )
                        
                        # Process the document
                        process_document_in_viewer(driver)
                        
                        # Close viewer and return to results
                        close_viewer(driver)
                        
                        # Wait for results page to load again
                        time.sleep(2)
                        
                    except Exception as e:
                        logging.error(f"Error processing document: {e}")
                        # Try to continue with next document
                        try:
                            close_viewer(driver)
                        except:
                            pass
                        continue
            else:
                logging.info("No documents found for today")
        else:
            logging.error("Search failed or no results found")
            
    except Exception as e:
        logging.error(f"Fatal error in main process: {e}")
        
    finally:
        try:
            driver.quit()
            logging.info("Monitoring completed")
        except Exception:
            pass

if __name__ == "__main__":
    main()
