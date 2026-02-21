# -*- coding: utf-8 -*-
"""
企業リサーチツール v3
====================
業種 x 地域 で企業サイトを検索し、
各サイトからメールアドレス・電話番号を収集してCSVに出力。

使い方:
  py business_research.py
"""

import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import os
import sys
import io
import json
import base64
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from datetime import datetime

# Windows UTF-8対応（ターミナル実行時のみ）
def setup_windows_console():
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass

# ===== 設定 =====
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 10
DELAY = 1.5

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'(?:0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4})')

BAD_DOMAINS = {
    "example.com", "test.com", "sentry.io", "wixpress.com",
    "w3.org", "schema.org", "googleapis.com", "googleusercontent.com",
    "gstatic.com", "facebook.com", "twitter.com", "instagram.com",
}

SKIP_DOMAINS = [
    # 汎用・SNS系
    "google.", "youtube.", "facebook.", "twitter.", "instagram.",
    "amazon.", "rakuten.", "yahoo.", "wikipedia.", "linkedin.",
    "tiktok.", "pinterest.", "github.", "microsoft.", "bing.", "note.com", "ameblo.jp",
    
    # 飲食系ポータル
    "tabelog.", "hotpepper.jp", "gnavi.", "retty.", "hitosara.", "ikyu.", "epark.",
    
    # 美容系ポータル
    "beauty.hotpepper.", "minimodel.", "ozmall.", "kamimabo.", "beauty-park.", "rakuten.co.jp/salon", "socie.",
    "hairbook.", "spc-net.", "macaron-hair.", "earth.", "beauty-navi.", "rasysa.", "epark.jp", "tiary.",
    
    # 不動産系ポータル
    "suumo.", "homes.", "athome.", "chintai.", "apaman.", "minimini.", "leopalace21.",
    
    # 求人ポータル・会社情報
    "indeed.", "doda.", "mynavi.", "rikunabi.", "en-japan.", "townwork.", "baitoru.",
    "bizreach.", "type.", "houjin.", "salesnow.", "baseconnect.", "syukatsu.",
    
    # その他のポータル・海外サイト
    "zhihu.", "baidu.", "naver.", "ekiten.", "jalan.", "travel.", "tripadvisor."
]


def banner():
    print("")
    print("=" * 55)
    print("  [BUSINESS RESEARCH TOOL]")
    print("  -- CSV --")
    print("=" * 55)
    print("")


def get_input():
    print("[STEP 0]")
    print("")
    print("  (: , , , Web)")
    industry = input("  >> ").strip()
    if not industry:
        print("  ERROR: !")
        return None, None, None

    print("")
    print("  (: , , , )")
    region = input("  >> ").strip()
    if not region:
        print("  ERROR: !")
        return None, None, None

    print("")
    count_str = input("  (default 20): ").strip()
    count = int(count_str) if count_str.isdigit() else 20
    count = min(count, 100)

    print("")
    print(f"  >>> [{industry}] x [{region}] max {count}")
    print("-" * 40)
    return industry, region, count


def decode_bing_url(href):
    """BingのリダイレクトURLから実際のURLを抽出"""
    if "/ck/a?" not in href:
        return href

    try:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        if "u" in params:
            encoded = params["u"][0]
            # "a1" プレフィックスを除去してBase64デコード
            if encoded.startswith("a1"):
                decoded = base64.b64decode(encoded[2:] + "==").decode("utf-8", errors="ignore")
                if decoded.startswith("http"):
                    return decoded
    except Exception:
        pass
    return href


def skip_url(url):
    domain = urlparse(url).netloc.lower()
    return any(s in domain for s in SKIP_DOMAINS)


def search_via_api(query, count=20, api_key=""):
    """Serper APIを使ってGoogle検索を確実に実行"""
    urls = []
    seen = set()
    url = "https://google.serper.dev/search"
    
    print(f"  [*] Serper API (Target: {count})")
    
    # 除外されて件数が減ることを考慮し、最大10ページ(約1000件分)まで検索して補填する
    for page in range(10): 
        if len(urls) >= count:
            break
            
        payload = json.dumps({
          "q": query,
          "gl": "jp",
          "hl": "ja",
          "num": 100,
          "page": page + 1
        })
        headers = {
          'X-API-KEY': api_key,
          'Content-Type': 'application/json'
        }
        
        try:
            time.sleep(DELAY)
            resp = requests.post(url, headers=headers, data=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if "organic" in data and len(data["organic"]) > 0:
                    for item in data["organic"]:
                        href = item.get("link", "")
                        if href.startswith("http") and not skip_url(href):
                            domain = urlparse(href).netloc
                            if domain not in seen:
                                seen.add(domain)
                                urls.append(href)
                                if len(urls) >= count:
                                    break # 目標件数に達したら即終了
                else:
                    break # もう検索結果がなければ終了
                
                print(f"  [*] API: {len(urls)} URLs so far...")
            else:
                print(f"  [!] API: HTTP {resp.status_code} - {resp.text}")
                break
        except Exception as e:
            print(f"  [!] API Error: {e}")
            break
            
    return urls[:count]


def search_bing(query, count=20):
    """Bing検索でURL取得"""
    urls = []
    seen = set()

    # 最大10ページ(約100件分)まで検索して補填する
    for page in range(10):
        if len(urls) >= count:
            break

        offset = page * 10
        try:
            time.sleep(DELAY)
            resp = requests.get(
                "https://www.bing.com/search",
                params={"q": query, "first": offset + 1, "count": 10},
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                print(f"  [!] Bing p{page+1}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select("li.b_algo")
            if not items:
                break # 検索結果がなくなったら終了

            for li in items:
                a = li.find("a", href=True)
                if a:
                    href = decode_bing_url(a["href"])
                    if href.startswith("http") and not skip_url(href):
                        domain = urlparse(href).netloc
                        if domain not in seen:
                            seen.add(domain)
                            urls.append(href)
                            if len(urls) >= count:
                                break # 目標件数に達したら即終了

            print(f"  [*] Bing p{page+1}: {len(urls)} URLs so far...")

        except Exception as e:
            print(f"  [!] Bing error: {e}")
            break

    return urls[:count]


def search_ddg(query, count=20):
    """DuckDuckGo HTML版で検索（フォールバック）"""
    urls = []
    seen = set()
    try:
        time.sleep(DELAY)
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return urls

        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.select("a.result__a[href]"):
            href = a.get("href", "")
            if "uddg=" in href:
                p = parse_qs(urlparse(href).query)
                if "uddg" in p:
                    href = unquote(p["uddg"][0])

            if href.startswith("http") and not skip_url(href):
                domain = urlparse(href).netloc
                if domain not in seen:
                    seen.add(domain)
                    urls.append(href)

        print(f"  [*] DuckDuckGo: {len(urls)} URLs")
    except Exception as e:
        print(f"  [!] DuckDuckGo error: {e}")

    return urls[:count]


def manual_url_input():
    """手動URL入力およびファイル読み込み"""
    print("")
    print("  --- URL収集に失敗しました ---")
    print("  以下のいずれかの方法でURLを指定してください：")
    print("")
    print("  1. 'urls.txt' という名前のファイルにURLを1行ずつ保存して、このフォルダに置く")
    print("  2. ここに直接URLを1つずつ貼り付ける（'done' で終了）")
    print("")
    
    urls = []
    
    # スクリプトと同じフォルダの urls.txt を探す
    script_dir = os.path.dirname(os.path.abspath(__file__))
    urls_file = os.path.join(script_dir, "urls.txt")
    
    if os.path.exists(urls_file):
        print(f"  [*] '{urls_file}' を発見しました。読み込み中...")
        with open(urls_file, "r", encoding="utf-8-sig") as f:
            for line in f:
                u = line.strip()
                if u.startswith("http"):
                    urls.append(u)
        if urls:
            print(f"  [+] {len(urls)} 件のURLをファイルから読み込みました。")
            return urls

    print("  (URLを入力してください。終わったら 'done' と打ってEnter)")
    while True:
        u = input("  URL: ").strip()
        if u.lower() == "done":
            break
        if not u:
            if urls:
                break
            continue
        if u.startswith("http"):
            urls.append(u)
            print(f"    -> 合計 {len(urls)} 件")
        else:
            print("    -> http:// または https:// で始まるURLを入れてください")
    return urls


def ok_email(email):
    e = email.lower()
    if len(e) < 5 or len(e) > 100:
        return False
    # ダミーメールを除外
    if any(x in e for x in ["sample", "example", "test", "domain", "admin@", "support@", "noreply"]):
        return False
    parts = e.split("@")
    if len(parts) != 2:
        return False
    domain = parts[1]
    if domain in BAD_DOMAINS:
        return False
    if domain.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js")):
        return False
    return True


def clean_phone(s):
    digits = re.sub(r'[^\d]', '', s)
    # ダミー番号を除外
    if digits in ["0000000000", "0123456789", "00000000000"]:
        return ""
        
    if 10 <= len(digits) <= 11 and digits.startswith("0"):
        if len(digits) == 10:
            return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
        elif digits.startswith("0120") or digits.startswith("0800"):
            return f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
        elif digits.startswith("03") or digits.startswith("06"):
            return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
        else:
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return ""


def get_title(soup):
    # まずog:site_nameやmetaタイトルを探す
    name = ""
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content"):
        name = og["content"].strip()
    
    if not name:
        t = soup.find("title")
        if t:
            name = t.get_text(strip=True)

    if name:
        # 余計なキャッチコピーや住所を削る（ | や - で区切られていることが多い）
        for sep in [" | ", " - ", " – ", " — ", "：", "｜"]:
            if sep in name:
                name = name.split(sep)[0].strip()
        # 長すぎる場合はカット
        return name[:50]
    return ""


def extract_with_llm(text, url, openai_api_key):
    """LLMを使ってテキストから代表連絡先を抽出する"""
    if not openai_api_key or not text.strip():
        return None
        
    prompt = f"""
以下の企業ウェブサイトのテキストから、代表となる問い合わせ用のメールアドレスと電話番号を1つずつ正確に抽出してください。
法人の代表連絡先としてふさわしくない個人のメールアドレスやダミーデータ（sample@等）は除外してください。
どうしても見つからない場合は該当項目を空文字にしてください。
必ず以下のJSON形式でのみ出力してください。他のテキストは一切不要です。
URL: {url}

{{
    "email": "抽出したメールアドレス",
    "phone": "抽出した電話番号"
}}

--- ウェブサイトテキスト ---
{text[:10000]}
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    
    try:
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        else:
            print(f"  [!] OpenAI API Error: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"  [!] OpenAI request failed: {e}")
        
    return None


def scrape_site(url, openai_api_key=""):
    """サイトからメアド・電話番号・法人名を抽出"""
    emails = set()
    phones = set()
    name = ""
    accumulated_text = ""

    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    paths = ["", "/contact", "/about", "/company", "/access"]

    for path in paths:
        try:
            time.sleep(0.5)
            r = requests.get(base + path, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code != 200:
                continue

            # 文字化け対策: apparent_encoding を使用
            r.encoding = r.apparent_encoding
            
            soup = BeautifulSoup(r.text, "lxml")
            if not name:
                name = get_title(soup)
                
            # LLM向けにテキストを蓄積
            if openai_api_key and len(accumulated_text) < 10000:
                accumulated_text += soup.get_text(separator="\n", strip=True) + "\n\n"

            # 従来のテキストからの抽出 (フォールバック / ベースライン処理)
            for m in EMAIL_RE.findall(r.text):
                if ok_email(m):
                    emails.add(m.lower())
            
            # mailto リンクからの抽出
            for a in soup.select("a[href^='mailto:']"):
                addr = a["href"].replace("mailto:", "").split("?")[0].strip()
                if addr and ok_email(addr):
                    emails.add(addr.lower())

            # 電話番号の抽出
            for m in PHONE_RE.findall(r.text):
                p = clean_phone(m)
                if p:
                    phones.add(p)
            for a in soup.select("a[href^='tel:']"):
                p = clean_phone(a["href"].replace("tel:", ""))
                if p:
                    phones.add(p)

        except Exception:
            continue
            
    # LLMによる高精度抽出（オプション）
    if openai_api_key and accumulated_text:
        llm_result = extract_with_llm(accumulated_text, url, openai_api_key)
        if llm_result:
            if llm_result.get("email") and ok_email(llm_result["email"]):
                emails.add(llm_result["email"].lower())
            if llm_result.get("phone"):
                p = clean_phone(llm_result["phone"])
                if p:
                    phones.add(p)

    return {
        "name": name or urlparse(url).netloc,
        "url": url,
        "emails": sorted(emails)[:3],
        "phones": sorted(phones)[:2],
    }


def save_csv(results, industry, region):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"企業リスト_{industry}_{region}_{ts}.csv"
    
    # Windowsのデスクトップパスをより確実に取得
    desktop = ""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
        desktop = winreg.QueryValueEx(key, "Desktop")[0]
    except Exception:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")

    if not os.path.isdir(desktop):
        desktop = os.getcwd()
        
    path = os.path.join(desktop, fname)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["法人名", "メールアドレス", "電話番号", "URL"])
        for r in results:
            w.writerow([
                r["name"],
                " / ".join(r["emails"]),
                " / ".join(r["phones"]),
                r["url"],
            ])
            
    # 保存したフォルダを自動で開く（Windowsローカル環境のみ）
    try:
        if os.name == 'nt' and hasattr(os, 'startfile'):
            os.startfile(os.path.dirname(path))
    except Exception:
        pass
        
    return path


def send_to_gsheet(results):
    """結果をGoogleスプレッドシート（GAS）に送信"""
    print("\n--- Googleスプレッドシート連携 ---")
    default_url = "https://script.google.com/macros/s/AKfycbzvixEvfoYYuJyx4HrHDQSawutXr37Jm1b54eJ-SNDKa7aT0q6bOsH2UcAwWsqQKSJH/exec"
    print(f"  現在の設定URL: {default_url}")
    print("  別のURLを使う場合は入力してください（そのまま使う場合はEnter）")
    gas_url = input("  URL: ").strip() or default_url
    
    if not gas_url:
        print("  [*] 連携をスキップしました。")
        return False

    print(f"  [*] {len(results)} 件のデータを送信中...")
    try:
        payload = {"results": results}
        # JSON で送信 (GAS側で JSON.parse できるように)
        resp = requests.post(gas_url, json=payload, timeout=20)
        
        if resp.status_code == 200:
            print("  [+] 送信成功！スプレッドシートを確認してください。")
            return True
        else:
            print(f"  [!] 送信失敗: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  [!] エラー発生: {e}")
        return False


def main():
    banner()
    industry, region, count = get_input()
    if not industry:
        return

    query = f"{industry} {region}"

    # STEP 1: URL検索
    print("")
    print(f"[STEP 1] [{query}] Bing...")
    print("")
    urls = search_bing(query, count)

    if len(urls) < 3:
        print("")
        print("  [*] Bing -> DuckDuckGo ...")
        ddg = search_ddg(query, count)
        seen = {urlparse(u).netloc for u in urls}
        for u in ddg:
            if urlparse(u).netloc not in seen:
                urls.append(u)
                seen.add(urlparse(u).netloc)

    if not urls:
        print("")
        print("  [!] URL")
        urls = manual_url_input()

    if not urls:
        print("  URL -> ")
        return

    print(f"\n  >>> {len(urls)} URL\n")

    # STEP 2: サイトスクレイピング
    print(f"[STEP 2] ...")
    print("")
    results = []

    for i, url in enumerate(urls, 1):
        domain = urlparse(url).netloc
        disp = domain[:35] + "..." if len(domain) > 35 else domain
        print(f"  [{i:3d}/{len(urls)}] {disp}", end=" ", flush=True)

        info = scrape_site(url)
        results.append(info)

        ec = len(info["emails"])
        pc = len(info["phones"])
        if ec or pc:
            parts = []
            if ec:
                parts.append(f"mail:{ec}")
            if pc:
                parts.append(f"tel:{pc}")
            print(f"-> OK ({', '.join(parts)})")
        else:
            print("-> --")

        time.sleep(DELAY)

    # STEP 3: CSV
    print("")
    print("[STEP 3] CSV...")

    with_info = [r for r in results if r["emails"] or r["phones"]]
    without = [r for r in results if not r["emails"] and not r["phones"]]
    all_sorted = with_info + without
    path = save_csv(all_sorted, industry, region)

    # 結果
    print("")
    print("=" * 55)
    print(f"  [{industry}] x [{region}]")
    print(f"  : {len(results)}")
    print(f"  mail : {len([r for r in results if r['emails']])}")
    print(f"  tel  : {len([r for r in results if r['phones']])}")
    print(f"  total: {len(with_info)}")
    print(f"")
    print(f"  CSV: {path}")
    print("=" * 55)

    if with_info:
        print(f"\n  (max 10):\n")
        for r in with_info[:10]:
            print(f"  [{r['name']}]")
            if r["emails"]:
                print(f"     Mail: {', '.join(r['emails'])}")
            if r["phones"]:
                print(f"     Tel:  {', '.join(r['phones'])}")
            print()

    # Googleスプレッドシート連携（追加）
    if with_info:
        send_to_gsheet(with_info)

    print("Done! CSV Excel!\n")


if __name__ == "__main__":
    main()
