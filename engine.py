import os
import requests
import asyncio
import re
import json
from datetime import datetime
from playwright_stealth import Stealth
from playwright.async_api import async_playwright, TimeoutError
import sys

from streamlit import context
# make sure subprocess support is available even when the engine is run
# outside Streamlit; same reasoning as in app.py
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# -------------------------
# Configuration
# -------------------------
CONFIG = {
    "timeout_navigation": 45000,
    "timeout_element": 15000,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
}

# -------------------------
# Global Utilities
# -------------------------
def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    invalid_chars = r'[<>:"/\\|?*]'
    return re.sub(invalid_chars, '_', filename).strip()

async def download_file_helper(url, filepath):
    """Generic file downloader with headers to mimic browser"""
    headers = {
        "User-Agent": CONFIG["user_agent"],
        "Referer": "https://www.google.com/"
    }
    if "nseindia" in url:
        headers["Referer"] = "https://www.nseindia.com/"
    elif "bseindia" in url:
        headers["Referer"] = "https://www.bseindia.com/"
        
    try:
        # Using requests for the actual file download which is more efficient for large files
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=60)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(response.content)
        return True, len(response.content)
    except Exception as e:
        return False, str(e)

# ---------------------------------------------------------
# BSE MODULE
# ---------------------------------------------------------
async def bse_get_company_info(page, company_input):
    """BSE discovery logic: Extract URL info or use scrip code search"""
    company_input = company_input.strip()
    
    # Direct Link Case
    if "bseindia.com/stock-share-price/" in company_input:
        match = re.search(r'/stock-share-price/([^/]+)/([^/]+)/(\d+)/', company_input)
        if match:
            return match.group(3), match.group(2), match.group(1), match.group(2)

    # Scrip Code Case
    if company_input.isdigit() and len(company_input) == 6:
        return company_input, "symbol", "company", company_input

    # Smart Search Discovery
    try:
        await page.goto("https://www.bseindia.com/getquote.aspx", wait_until="networkidle", timeout=CONFIG["timeout_navigation"])
        search_input = "input#ContentPlaceHolder1_SmartSearch_smartSearch"
        suggestion_selector = "#ajax_response_smart li a"
        
        await page.wait_for_selector(search_input, timeout=CONFIG["timeout_element"])
        await page.focus(search_input)
        
        for char in company_input[:30]:
            await page.keyboard.press(char)
            await asyncio.sleep(0.1)
        
        try:
            await page.wait_for_selector(suggestion_selector, timeout=10000)
            links = await page.locator(suggestion_selector).all()
            if links:
                for link in links:
                    text = await link.inner_text()
                    match_codes = re.findall(r'(\d{6})', text)
                    if match_codes:
                        scrip_code = match_codes[-1]
                        company_name = text.splitlines()[0] if text.splitlines() else company_input
                        return scrip_code, "symbol", "company", company_name
        except:
            pass

        await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle", timeout=CONFIG["timeout_navigation"])
        final_url = page.url
        match = re.search(r'/stock-share-price/([^/]+)/([^/]+)/(\d+)/', final_url)
        if match:
            return match.group(3), match.group(2), match.group(1), company_input
    except Exception as e:
        print(f"   [BSE-ERROR] Discovery failed: {e}")
    return None, None, None, None

async def bse_extract_reports(page):
    reports = []
    try:
        try:
            await page.wait_for_selector("td:has-text('Year')", timeout=10000)
        except:
            await page.wait_for_selector("table", timeout=5000)
        
        table_loc = page.locator("table").filter(has=page.locator("td:has-text('Year')")).last
        if not table_loc: return reports

        rows = await table_loc.locator("tr").all()
        for row in rows:
            cells = await row.locator("td").all()
            if not cells: continue
            
            period_text = (await cells[0].inner_text()).strip()
            if not period_text or not any(char.isdigit() for char in period_text):
                continue
            
            links = await row.locator("a").all()
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    h_lower = href.lower()
                    if any(x in h_lower for x in [".pdf", "/AttachHis/", "/AnnualReport/", "/HISTANNR/"]):
                        reports.append({
                            "year_str": period_text,
                            "link": href if href.startswith("http") else f"https://www.bseindia.com{href}"
                        })
                        break
    except Exception as e:
        print(f"   [BSE-ERROR] Extraction failed: {e}")
    return reports

# ---------------------------------------------------------
# NSE MODULE
# ---------------------------------------------------------
async def nse_get_company_info(company_input):
    """NSE discovery via autocomplete API"""
    headers = {"User-Agent": CONFIG["user_agent"], "Accept": "application/json"}
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=15)
        search_url = f"https://www.nseindia.com/api/search/autocomplete?q={company_input}"
        response = session.get(search_url, headers=headers, timeout=15)
        data = response.json()
        
        results = []
        if isinstance(data, list): results = data
        elif isinstance(data, dict):
            results = data.get("symbols", []) or data.get("data", [])
            
        if results:
            first = results[0]
            return first.get("symbol"), first.get("companyName") or first.get("symbol")
    except Exception as e:
        print(f"   [NSE-ERROR] API discovery failed: {e}")
    return None, None

async def nse_extract_reports(page, target_year):
    reports = []
    target_short = str(target_year + 1)[-2:]
    year_pattern = f"{target_year}-{target_short}"
    
    try:
        await page.wait_for_selector("a[href$='.pdf'], a[href$='.zip']", timeout=15000)
        links = await page.locator("a[href$='.pdf'], a[href$='.zip']").all()
        
        for link_el in links:
            href = await link_el.get_attribute("href") or ""
            text = (await link_el.text_content()) or ""
            if str(target_year) in text or year_pattern in text or str(target_year) in href or year_pattern in href:
                reports.append({
                    "year_str": year_pattern,
                    "link": href if href.startswith("http") else f"https://www.nseindia.com{href}"
                })
                break
    except:
        pass
    return reports

# ---------------------------------------------------------
# ENGINE INTERFACE
# ---------------------------------------------------------
class ReportEngine:
    def __init__(self, logger=print):
        self.logger = logger

    async def run_bse(self, company_query, target_year, download_dir):
        os.makedirs(download_dir, exist_ok=True)
        # async with async_playwright() as p:
        #     browser = await p.chromium.launch(headless=True)
        #     context = await browser.new_context(user_agent=CONFIG["user_agent"])
        #     page = await context.new_page()
        #     stealth = Stealth()
        #     await stealth.apply_stealth_async(page, Stealth.config())
        stealth = Stealth()
        async with stealth.use_async(async_playwright()) as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=CONFIG["user_agent"])
            page = await context.new_page()
            
            try:
                stock_code, symbol, slug, name = await bse_get_company_info(page, company_query)
                if not stock_code:
                    self.logger(f"[BSE] Company not found: {company_query}")
                    return False

                self.logger(f"[BSE] Found: {name} ({stock_code})")
                url = f"https://www.bseindia.com/stock-share-price/{slug}/{symbol}/{stock_code}/financials-annual-reports/"
                await page.goto(url, wait_until="domcontentloaded", timeout=CONFIG["timeout_navigation"])
                await asyncio.sleep(2)
                
                reports = await bse_extract_reports(page)
                for r in reports:
                    year_text = r['year_str'].lower()
                    target_str = str(target_year)
                    target_short = target_str[-2:]
                    
                    if target_str in year_text or (f"-{target_short}" in year_text) or (f"/{target_short}" in year_text):
                        filename = sanitize_filename(f"BSE_{name}_{target_year}_AnnualReport.pdf")
                        filepath = os.path.join(download_dir, filename)
                        success, info = await download_file_helper(r['link'], filepath)
                        if success:
                            self.logger(f"[OK] BSE Downloaded: {filename} ({info/1024/1024:.2f} MB)")
                            return True
                        else:
                            self.logger(f"[FAIL] BSE Download failed: {info}")
                
                self.logger(f"[BSE] No report for {target_year}")
            except Exception as e:
                self.logger(f"[BSE-ERROR] {e}")
            finally:
                await browser.close()
        return False

    async def run_nse(self, company_query, target_year, download_dir):
        os.makedirs(download_dir, exist_ok=True)
        symbol, name = await nse_get_company_info(company_query)
        if not symbol:
            self.logger(f"[NSE] Company not found: {company_query}")
            return False

        self.logger(f"[NSE] Found: {name} ({symbol})")
        # async with async_playwright() as p:
        #     browser = await p.chromium.launch(headless=True)
        #     context = await browser.new_context(user_agent=CONFIG["user_agent"])
        #     page = await context.new_page()
        #     stealth = Stealth()
        #     await stealth.apply_stealth_async(page, Stealth.config())
        stealth = Stealth()
        async with stealth.use_async(async_playwright()) as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=CONFIG["user_agent"])
            page = await context.new_page()
        
            
            try:
                await page.goto("https://www.nseindia.com", wait_until="networkidle", timeout=CONFIG["timeout_navigation"])
                url = f"https://www.nseindia.com/companies-listing/corporate-filings-annual-reports?symbol={symbol}"
                await page.goto(url, wait_until="networkidle", timeout=CONFIG["timeout_navigation"])
                await asyncio.sleep(3)
                
                reports = await nse_extract_reports(page, target_year)
                if reports:
                    r = reports[0]
                    filename = sanitize_filename(f"NSE_{name}_{target_year}_AnnualReport.pdf")
                    filepath = os.path.join(download_dir, filename)
                    success, info = await download_file_helper(r['link'], filepath)
                    if success:
                        self.logger(f"[OK] NSE Downloaded: {filename} ({info/1024/1024:.2f} MB)")
                        return True
                    else:
                        self.logger(f"[FAIL] NSE Download failed: {info}")
                else:
                    self.logger(f"[NSE] No report for {target_year}")
            except Exception as e:
                self.logger(f"[NSE-ERROR] {e}")
            finally:
                await browser.close()
        return False

if __name__ == "__main__":
    # Test script
    engine = ReportEngine()
    asyncio.run(engine.run_bse("Reliance", 2024, "test_downloads"))
