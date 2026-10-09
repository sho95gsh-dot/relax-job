import datetime
import json
import os
import gspread
from playwright.sync_api import sync_playwright

def setup_gspread():
    creds_json = os.environ.get("GCP_SA_KEY")
    if not creds_json:
        raise ValueError("Secretsに GCP_SA_KEY が設定されていません")
    creds_dict = json.loads(creds_json)

    client = gspread.service_account_from_dict(creds_dict)
    sheet = client.open("リジョブ新店リスト").sheet1
    return sheet

def scrape_rejob():
    new_jobs = []
    target_url = "https://relax-job.com/search?business_type=biyoshi.riyoshi&city=28201.28210.28216.28229.28381.28382.28464&employment=arbeit.business-consignment.contract-employee.other.regular-member&facility_type=barber-shop.hair-salon.haircolor-shop.haircut-shop.spa&pref=28&sort=new"

    with sync_playwright() as p:
        # ブラウザを起動
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"Accessing: {target_url}")
        page.goto(target_url, wait_until="domcontentloaded")
        
        # 画面の求人データが表示されるまで5秒待機する
        page.wait_for_timeout(5000)

        # 求人の枠を探す
        cards = page.query_selector_all("article, .job-card, .search-result-item, .job-item")
        today = datetime.date.today().strftime("%Y-%m-%d")

        print(f"画面から {len(cards)} 件の求人カードを発見しました。")

        for card in cards:
            try:
                title_elem = card.query_selector("h2, h3, .job-card__title, .title")
                title = title_elem.inner_text().strip() if title_elem else "不明"

                link_elem = card.query_selector("a")
                href = link_elem.get_attribute("href") if link_elem else ""
                full_url = (
                    f"https://relax-job.com{href}"
                    if href.startswith("/")
                    else href
                )

                company_elem = card.query_selector(".company-name, .job-card__company, .company")
                company = company_elem.inner_text().strip() if company_elem else "不明"

                location_elem = card.query_selector(".location, .job-card__location, .access")
                location = location_elem.inner_text().strip() if location_elem else "不明"

                if title != "不明" and full_url:
                    new_jobs.append([today, company, title, location, full_url])

            except Exception as e:
                continue

        browser.close()

    return new_jobs

def main():
    sheet = setup_gspread()
    existing_urls = sheet.col_values(5)

    jobs = scrape_rejob()
    rows_to_add = []

    for job in jobs:
        url = job[4]
        if url not in existing_urls:
            rows_to_add.append(job)

    if rows_to_add:
        sheet.append_rows(rows_to_add)
        print(f"スプレッドシートに {len(rows_to_add)} 件の新店求人を追加しました。")
    else:
        print("新しい求人は見つかりませんでした。")

if __name__ == "__main__":
    main()
