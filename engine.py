import os
import requests
from utils import sanitize_filename

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

class ReportEngine:
    def __init__(self, logger=print):
        self.log = logger

    # ---------------- NSE ----------------
    async def run_nse(self, company, year, save_dir):
        os.makedirs(save_dir, exist_ok=True)

        self.log(f"[NSE] Searching for {company}")

        try:
            session = requests.Session()
            session.get("https://www.nseindia.com", headers=HEADERS)

            search_url = f"https://www.nseindia.com/api/search/autocomplete?q={company}"
            data = session.get(search_url, headers=HEADERS).json()

            symbol = data["symbols"][0]["symbol"]
            name = data["symbols"][0]["symbol"]

            ann_url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={symbol}"
            reports = session.get(ann_url, headers=HEADERS).json()

            for r in reports:
                if "Annual Report" in r.get("subject", ""):
                    link = r.get("attchmntFile")

                    filename = sanitize_filename(f"NSE_{company}_{year}.pdf")
                    path = os.path.join(save_dir, filename)

                    self.download(link, path)

                    self.log(f"✔ NSE Downloaded: {filename}")
                    return True

            self.log("[NSE] No report found")

        except Exception as e:
            self.log(f"[NSE ERROR] {e}")

        return False

    # ---------------- BSE ----------------
    async def run_bse(self, company, year, save_dir):
        os.makedirs(save_dir, exist_ok=True)

        self.log(f"[BSE] Searching for {company}")

        try:
            search_url = f"https://api.bseindia.com/BseIndiaAPI/api/SmartSearch/w?q={company}"
            data = requests.get(search_url, headers=HEADERS).json()

            if not data:
                self.log("[BSE] Company not found")
                return False

            scrip = data[0]["ScripCode"]

            report_url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnualReport/w?strScrip={scrip}"
            reports = requests.get(report_url, headers=HEADERS).json()

            for r in reports:
                if str(year) in r.get("FinancialYear", ""):
                    link = r.get("AttachmentPath")

                    filename = sanitize_filename(f"BSE_{company}_{year}.pdf")
                    path = os.path.join(save_dir, filename)

                    self.download(link, path)

                    self.log(f"✔ BSE Downloaded: {filename}")
                    return True

            self.log("[BSE] No report found")

        except Exception as e:
            self.log(f"[BSE ERROR] {e}")

        return False

    # ---------------- DOWNLOAD ----------------
    def download(self, url, path):
        r = requests.get(url, headers=HEADERS)
        with open(path, "wb") as f:
            f.write(r.content)
