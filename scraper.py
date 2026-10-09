import datetime
import json
import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright


def setup_gspread():
    # GitHub Secretsから認証情報を読み込み
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_json = os.environ.get("GCP_SA_KEY")
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    # スプレッドシート名で開く
    sheet = client.open("リジョブ新店リスト").sheet1
    return sheet


def scrape_rejob():
    new_jobs = []
    # リジョブのオープニング求人検索URL（適宜ターゲットエリアや職種で絞り込んだURLに変更可能）
    target_url = "https://relax-job.com/search?keyword=%E3%82%AA%E3%83%BC%E3%83%97%E3%83%8B%E3%83%B3%E3%82%B0"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Bot検知を回避するためのUser-Agent設定
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"Accessing: {target_url}")
        page.goto(target_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)  # 動的コンテンツの読み込み待ち

        # 求人カード要素の取得（サイト構造変更に対応できるよう調整）
        cards = page.query_selector_all("article, .job-card, .search-result-item")

        today = datetime.date.today().strftime("%Y-%m-%d")

        for card in cards:
            try:
                text_content = card.inner_text()

                # タイトルや店舗名の抽出
                title_elem = card.query_selector("h2, h3, .job-card__title")
                title = title_elem.inner_text().strip() if title_elem else "不明"

                # リンクの取得
                link_elem = card.query_selector("a")
                href = link_elem.get_attribute("href") if link_elem else ""
                full_url = (
                    f"https://relax-job.com{href}"
                    if href.startswith("/")
                    else href
                )

                # 店舗名/企業名の取得
                company_elem = card.query_selector(
                    ".company-name, .job-card__company"
                )
                company = (
                    company_elem.inner_text().strip()
                    if company_elem
                    else "不明"
                )

                # エリア情報の取得
                location_elem = card.query_selector(
                    ".location, .job-card__location"
                )
                location = (
                    location_elem.inner_text().strip()
                    if location_elem
                    else "不明"
                )

                if title != "不明" and full_url:
                    new_jobs.append(
                        [today, company, title, location, full_url]
                    )

            except Exception as e:
                print(f"Error parsing card: {e}")
                continue

        browser.close()

    return new_jobs


def main():
    sheet = setup_gspread()

    # 既存のURL一覧を取得して重複登録を防ぐ
    existing_urls = sheet.col_values(5)  # 5列目（E列）がURL

    jobs = scrape_rejob()
    rows_to_add = []

    for job in jobs:
        url = job[4]
        if url not in existing_urls:
            rows_to_add.append(job)

    if rows_to_add:
        sheet.append_rows(rows_to_add)
        print(f"{len(rows_to_add)} 件の新店求人を追加しました。")
    else:
        print("新しい求人は見つかりませんでした。")


if __name__ == "__main__":
    main()
