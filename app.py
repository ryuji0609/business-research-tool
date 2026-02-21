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

# --- SaaS ログイン・ユーザー管理機能 ---
import requests
import json

def check_login():
    """GAS API（DB）に問い合わせてログインを行う"""
    manager_url = st.secrets.get("MANAGER_GAS_URL", "")
    
    # マネージャーURLが未設定の場合（ローカル開発用など）は通過させる
    if not manager_url:
        st.session_state["user_info"] = {
            "gas_url": st.secrets.get("GAS_URL", ""),
            "current_usage": 0,
            "max_usage": 1000
        }
        return True

    if "user_info" in st.session_state:
        return True

    # ログイン済でなければログイン画面を表示
    st.markdown("## 🔒 会員専用ログイン")
    st.info("SaaS版 企業リサーチツールへようこそ。発行されたIDとパスワードを入力してください。")
    
    with st.form("login_form"):
        user_id = st.text_input("ユーザーID")
        password = st.text_input("パスワード", type="password")
        submit_button = st.form_submit_button("ログイン")
        
        if submit_button:
            if not user_id or not password:
                st.error("IDとパスワードを入力してください。")
                return False
                
            with st.spinner("認証中..."):
                try:
                    payload = {
                        "action": "login",
                        "user_id": user_id,
                        "password": password
                    }
                    response = requests.post(manager_url, json=payload, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            st.session_state["user_info"] = {
                                "user_id": user_id,
                                "gas_url": result.get("gas_url"),
                                "current_usage": result.get("current_usage"),
                                "max_usage": result.get("max_usage")
                            }
                            st.session_state["password"] = password # API消費用に保持
                            st.rerun()
                        else:
                            st.error(f"ログイン失敗: {result.get('message')}")
                    else:
                        st.error(f"サーバーエラー: {response.status_code}")
                except Exception as e:
                    st.error(f"通信エラーが発生しました: {e}")
            return False
            
    return False

# ログインしていない場合はここでストップ
if not check_login():

    st.stop()


# --- スタイル（近未来モダンUI / スマホ完全対応） ---
st.markdown("""
    <style>
    /* 全体背景とフォント */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Noto Sans JP', sans-serif;
    }
    
    /* ヘッダー周りの非表示（クリーンなSaaSにするため） */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* メインタイトルグラデーション */
    h1 {
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900 !important;
        letter-spacing: -1px;
        margin-bottom: 0.5rem;
    }
    
    /* サブタイトル */
    .stMarkdown p {
        font-size: 1.05rem;
        color: #555555;
    }

    /* 実行ボタンの超リッチ化（スマホでも押しやすく） */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5rem;
        background: linear-gradient(135deg, #0cebeb 0%, #20e3b2 50%, #29ffc6 100%);
        color: #1a1a1a;
        font-size: 1.2rem;
        font-weight: bold;
        border: none;
        box-shadow: 0 4px 15px rgba(41, 255, 198, 0.4);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(41, 255, 198, 0.6);
        background: linear-gradient(135deg, #29ffc6 0%, #20e3b2 50%, #0cebeb 100%);
        color: #000;
    }
    .stButton>button:active {
        transform: translateY(1px);
    }
    
    /* プログレスバーのリッチ化 */
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #4facfe 0%, #00f2fe 100%);
        border-radius: 10px;
    }
    
    /* メトリック（利用状況）のカード化 */
    [data-testid="stMetricValue"] {
        font-size: 2.5rem !important;
        font-weight: 900 !important;
        color: #4facfe !important;
    }
    
    /* モバイル向け入力フォームの調整 */
    .stTextInput > div > div > input, .stNumberInput > div > div > input {
        border-radius: 8px;
        padding: 0.8rem;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
    }
    .stTextInput > div > div > input:focus, .stNumberInput > div > div > input:focus {
        border-color: #4facfe;
        box-shadow: 0 0 0 2px rgba(79, 172, 254, 0.2);
    }
    
    /* 会員ログインのコンテナ装飾 */
    [data-testid="stForm"] {
        background: #ffffff;
        padding: 2rem;
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        border: 1px solid #f0f0f0;
    }
    </style>
    """, unsafe_allow_html=True)


# --- サイドバー設定 ---
with st.sidebar:
    st.markdown("## 🚀 Dashboard")
    user_info = st.session_state.get("user_info", {})
    user_id = user_info.get('user_id', '未設定')
    current_usage = user_info.get('current_usage', 0)
    max_usage = user_info.get('max_usage', 0)
    
    st.markdown(f"**こんにちは、{user_id}さん！**")
    
    # リッチなダッシュボード表示
    st.metric(label="本日の残り利用可能枠", value=f"{max_usage - current_usage} 件", delta=f"/{max_usage} 上限", delta_color="off")
    
    st.divider()
    
    st.title("⚙️ 設定")
    gas_url = st.text_input(
        "Googleスプレッドシート (GAS URL)",
        value=user_info.get('gas_url', ''),
        help="あなた専用のデータ保存先です。"
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
st.markdown("<h1>✨直営業を自動化する 企業リサーチツール Pro</h1>", unsafe_allow_html=True)
st.write("ターゲットにする「業種」と「地域」を入れるだけで、AIが瞬時に営業先リストを生成。あなただけの最強の営業データベースを作り上げます。")
st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    industry = st.text_input("🎯 業種", placeholder="例: 美容院, 飲食店, Web制作会社")
with col2:
    region = st.text_input("📍 地域", placeholder="例: 埼玉県, 渋谷区, 大阪")
with col3:
    max_usage_limit = st.session_state.get("user_info", {}).get("max_usage", 1000) - st.session_state.get("user_info", {}).get("current_usage", 0)
    max_count = st.number_input("📥 取得件数", min_value=1, max_value=max(1, max_usage_limit), value=min(50, max(1, max_usage_limit)), step=10, help=f"本日の残り利用可能枠: {max_usage_limit}件")


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
            
            # 取得したURLリストを利用上限枠に合わせてカット
            user_info = st.session_state.get("user_info", {})
            current_usage = user_info.get("current_usage", 0)
            max_usage = user_info.get("max_usage", 1000)
            available = max_usage - current_usage
            
            if available <= 0:
                st.error(f"本日の利用上限（{max_usage}件）に達しています。明日またご利用ください。")
                st.stop()
                
            if len(urls) > available:
                st.warning(f"本日の残り上限（{available}件）を超えるため、{available}件に制限して取得します。")
                urls = urls[:available]
                
            # --- API消費処理（SaaS DBへ連絡） ---
            manager_url = st.secrets.get("MANAGER_GAS_URL", "")
            user_id = user_info.get("user_id")
            password_used = st.session_state.get("password")
            consume_count = len(urls)
            
            if manager_url and user_id and password_used and consume_count > 0:
                try:
                    resp = requests.post(manager_url, json={
                        "action": "consume",
                        "user_id": user_id,
                        "password": password_used,
                        "count": consume_count
                    }, timeout=5)
                    if resp.status_code == 200 and resp.json().get("success"):
                        st.session_state["user_info"]["current_usage"] = resp.json().get("current_usage")
                except Exception as e:
                    pass # エラー時はとりあえず処理を続行
            # ----------------------------------
            
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
