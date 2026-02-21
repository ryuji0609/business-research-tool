import streamlit as st
import pandas as pd
import time
import os
import sys
import importlib.util
from urllib.parse import urlparse

# business_research.py をパスに追加してインポート可能にする
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

try:
    import business_research as core
except ImportError:
    st.error("business_research.py が見つかりません。同一フォルダに配置してください。")
    st.stop()

# --- ページ設定 ---
st.set_page_config(
    page_title="企業リサーチツール Pro",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- スタイル ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #007bff;
        color: white;
    }
    .stProgress > div > div > div > div {
        background-color: #007bff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- サイドバー設定 ---
with st.sidebar:
    st.title("⚙️ 設定")
    gas_url = st.text_input(
        "Googleスプレッドシート (GAS URL)",
        value="https://script.google.com/macros/s/AKfycbzvixEvfoYYuJyx4HrHDQSawutXr37Jm1b54eJ-SNDKa7aT0q6bOsH2UcAwWsqQKSJH/exec",
        help="GASをデプロイした際の発行URLを入力してください。"
    )
    # クラウド（またはローカル設定）のSecretsからキーを安全に読み込む
    default_serper = st.secrets.get("SERPER_API_KEY", "") if "SERPER_API_KEY" in st.secrets else ""
    default_openai = st.secrets.get("OPENAI_API_KEY", "") if "OPENAI_API_KEY" in st.secrets else ""

    serper_api_key = st.text_input(
        "Serper APIキー (検索ブロック回避用)",
        value=default_serper,
        type="password",
        help="1日に何百件も検索する際に、Googleからのブロックを回避するためのAPIキーです"
    )
    openai_api_key = st.text_input(
        "OpenAI APIキー (AIによる超高精度抽出用)",
        value=default_openai,
        type="password",
        help="サイトのテキストからAIが代表連絡先を正確に抽出するためのキーです"
    )
    st.divider()    
    st.info("このツールは、指定した条件で企業情報を収集し、CSV保存とスプレッドシートへの送信を行います。")

# --- メイン画面 ---
st.title("🔍 企業リサーチツール Pro")
st.write("業種と地域を入力して、ターゲット企業の連絡先を瞬時にリストアップします。")

col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    industry = st.text_input("業種", placeholder="例: 美容院, 飲食店, Web制作会社")
with col2:
    region = st.text_input("地域", placeholder="例: 埼玉県, 渋谷区, 大阪")
with col3:
    max_count = st.number_input("最大取得件数", min_value=1, max_value=500, value=50, step=10)

# urls.txt の読み込み（あれば）
urls_file = os.path.join(script_dir, "urls.txt")
use_urls_txt = False
urls_in_file = []
if os.path.exists(urls_file):
    try:
        with open(urls_file, "r", encoding="utf-8-sig") as f:
            urls_in_file = [line.strip() for line in f if line.strip().startswith("http")]
    except Exception:
        pass

manual_urls_input = ""
if urls_in_file:
    use_urls_txt = st.checkbox(
        f"📁 登録済みの URL リストを使用する ({len(urls_in_file)} 件)", 
        value=False,
        help="urls.txt のリストを優先して処理します。"
    )
    if use_urls_txt:
        st.info("⚠️ 登録済みリストモードです。下のキーワード検索は無視されます。")
else:
    # urls.txt がない、または空の場合のフォールバック
    with st.expander("🔗 手動でURLを直接入力する"):
        manual_urls_input = st.text_area(
            "URLを1行ずつ貼り付けてください",
            placeholder="https://example.com\nhttps://test.jp",
            help="検索がうまくいかない場合や、特定のサイトだけ調べたい時に便利です。"
        )

start_button = st.button("🚀 リサーチ開始")

if start_button:
    results = []
    urls = []

    if use_urls_txt:
        urls = urls_in_file
    elif manual_urls_input.strip():
        urls = [u.strip() for u in manual_urls_input.split("\n") if u.strip().startswith("http")]
    
    if not urls and (not industry or not region):
        st.warning("業種と地域を入力するか、手動でURLを入力してください。")
    else:
        with st.status("🔍 調査中...", expanded=True) as status:
            # 1. URL収集
            if urls:
                st.write(f"✅ {len(urls)} 件のURLを読み込みました。")
            else:
                query = f"{industry} {region}"
                
                if serper_api_key:
                    st.write(f"⚡ 高速検索APIを使用して {query} を検索中...")
                    urls = core.search_via_api(query, max_count, serper_api_key)
                else:
                    st.write(f"🌎 {query} を検索中... (ブロックされる可能性があります。API設定を推奨)")
                    urls = core.search_bing(query, max_count)
                    if len(urls) < 3:
                       st.write("DuckDuckGo で追加のURLを検索中...")
                       ddg = core.search_ddg(query, max_count)
                       seen = {urlparse(u).netloc for u in urls}
                       for u in ddg:
                           if urlparse(u).netloc not in seen:
                               urls.append(u)
                               seen.add(urlparse(u).netloc)
            
            if not urls:
                st.error("URLの取得に失敗しました。")
                if not serper_api_key:
                    st.info("💡 対策: 検索エンジンにブロックされています。左側メニューの「Serper APIキー」を設定すると回避できます。")
                st.stop()
            
            st.write(f"✅ {len(urls)} 件の対象URLを特定しました。")
            
            progress_bar = st.progress(0)
            data_container = st.empty()
            df_preview = pd.DataFrame()
            
            for i, url in enumerate(urls, 1):
                st.write(f"[{i}/{len(urls)}] {urlparse(url).netloc} を解析中...")
                info = core.scrape_site(url, openai_api_key)
                
                if info["emails"] or info["phones"]:
                    parts = []
                    if info["emails"]: parts.append(f"メール等取得")
                    if info["phones"]: parts.append(f"電話番号取得")
                    st.write(f"  👉 取得成功: {' / '.join(parts)}")
                    
                    results.append(info)
                    
                    # 途中結果のプレビュー表示（有効なもののみ）
                    df_preview = pd.DataFrame([
                        {
                            "法人名": r["name"],
                            "メール": " / ".join(r["emails"]),
                            "電話": " / ".join(r["phones"]),
                            "URL": r["url"]
                        } for r in results
                    ])
                    data_container.dataframe(df_preview, use_container_width=True)
                else:
                    st.write("  ↳ ⚠️ 連絡先がひとつも見つかりませんでした（スキップ）")
                
                progress_bar.progress(i / len(urls))
                time.sleep(core.DELAY)
            
            status.update(label="✅ 調査完了しました！", state="complete", expanded=False)

        # 3. 結果の表示と保存
        st.success(f"計 {len(results)} 件の情報を取得しました。")
        
        # CSV保存（ローカル実行時用）
        csv_path = core.save_csv(results, industry, region)
        st.info(f"💾 CSVデータをエクスポートしました: {os.path.basename(csv_path)}")
        
        # Webブラウザからのダウンロードボタン（SaaSクラウド実行時用）
        csv_data = df_preview.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="⬇️ CSVファイルをダウンロード",
            data=csv_data,
            file_name=os.path.basename(csv_path),
            mime="text/csv",
            type="primary"
        )
        
        # スプレッドシート送信
        if gas_url:
            with st.spinner("📤 Googleスプレッドシートに送信中..."):
                with_info = [r for r in results if r["emails"] or r["phones"]]
                payload = {"results": with_info}
                try:
                    import requests
                    resp = requests.post(gas_url, json=payload, timeout=20)
                    if resp.status_code == 200:
                        st.balloons()
                        st.success("✨ Googleスプレッドシートへ自動送信しました！")
                    else:
                        st.error(f"スプレッドシート送信に失敗しました (HTTP {resp.status_code})")
                except Exception as e:
                    st.error(f"送信時にエラーが発生しました: {e}")

        # 詳細表示
        with st.expander("詳細データを表示"):
            st.table(df_preview)
