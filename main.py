import os
import uuid
import numpy as np
import traceback
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
import markdown
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import pytz

# --- 定数と設定 ---
# Secrets
USER_PASSWORD = os.getenv("USER_PASSWORD")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Google Sheets
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "FB")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")

# パス関連
FONT_PATH = 'fonts/MPLUS1p-Regular.ttf'
PROMPTS_DIR = "prompts"
DEFAULT_PROMPT_FILE = "default_report.txt"
VECTOR_DB_PATH = "vectorstore/db_faiss"
STATIC_DIR = "static"

# レーダーチャート関連
RADAR_CHART_METRICS = [
    "充実性", "会話性", "交流性", "幸福性", "表出性", "共感性", "尊重性", "融和性", "開示性", "創造性",
    "自立性", "感受性"
]
RADAR_CHART_AVG_SCORE = 22
RADAR_CHART_MAX_SCORE = 40

# LLM関連
RETRIEVER_SEARCH_K = 5

# タイムゾーン
JST = pytz.timezone('Asia/Tokyo')


# --- 初期設定 ---
load_dotenv()
app = Flask(__name__)


# --- 外部サービスへの接続 ---
try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)
    print("--- Google Sheetsへの接続完了 ---")
except gspread.exceptions.GSpreadException as e:
    print(f"エラー: Google Sheetsへの接続に失敗しました。認証情報やIDを確認してください。 {e}")
    worksheet = None
except Exception as e: # その他の予期せぬエラー
    print(f"エラー: Google Sheetsへの接続中に予期せぬ問題が発生しました。 {e}")
    worksheet = None

# 日本語フォントのパスを指定
if os.path.exists(FONT_PATH):
    font_prop = fm.FontProperties(fname=FONT_PATH)
else:
    print(f"警告: 日本語フォントファイルが見つかりません: {FONT_PATH}")
    font_prop = None


def create_radar_chart(scores_dict):
    """レーダーチャート画像を生成し、そのURLを返す"""
    values = [float(scores_dict.get(k, 0)) for k in RADAR_CHART_METRICS]
    avg_values = [RADAR_CHART_AVG_SCORE] * len(RADAR_CHART_METRICS)

    # プロットを閉じるために始点と終点を合わせる
    values_plot = values + [values[0]]
    avg_values_plot = avg_values + [avg_values[0]]

    angles = np.linspace(0, 2 * np.pi, len(RADAR_CHART_METRICS),
                         endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_ylim(0, RADAR_CHART_MAX_SCORE)
    ax.set_rgrids([10, 20, 30, RADAR_CHART_MAX_SCORE], angle=0)
    ax.set_xticks(angles[:-1])
    if font_prop:
        ax.set_xticklabels(RADAR_CHART_METRICS, fontproperties=font_prop, size=12)
    else:
        ax.set_xticklabels(RADAR_CHART_METRICS, size=12)

    ax.plot(angles, values_plot, color='red', linewidth=2.5)
    ax.fill(angles, values_plot, 'red', alpha=0.25)
    ax.plot(angles, avg_values_plot, color='blue', linewidth=1, linestyle='-')

    filename = f"chart_{uuid.uuid4()}.png"
    filepath = os.path.join(STATIC_DIR, filename)
    plt.savefig(filepath, bbox_inches='tight', pad_inches=0.2)
    plt.close(fig)
    return f"/{STATIC_DIR}/{filename}"


def load_prompt(template_name=DEFAULT_PROMPT_FILE):
    """プロンプトファイルを読み込む"""
    try:
        with open(os.path.join(PROMPTS_DIR, template_name),
                  "r",
                  encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"エラー: プロンプトファイルが見つかりません: {os.path.join(PROMPTS_DIR, template_name)}")
        return None


# --- LLMとベクトルDBの準備 ---
llm = None
retriever = None
try:
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7)
    embeddings = OpenAIEmbeddings()
    if os.path.exists(VECTOR_DB_PATH):
        vector_db = FAISS.load_local(VECTOR_DB_PATH,
                                     embeddings,
                                     allow_dangerous_deserialization=True)
        retriever = vector_db.as_retriever(search_kwargs={'k': RETRIEVER_SEARCH_K})
        print("--- LLMとベクトルデータベースの読み込み完了 ---")
    else:
        print(f"--- 警告: ベクトルデータベースが '{VECTOR_DB_PATH}' に見つかりません。レポート生成機能は利用できません。 ---")
except Exception as e:
    print(f"エラー: 初期設定中に問題が発生しました。 {e}")
    traceback.print_exc()

prompt_template_string = load_prompt()
if not prompt_template_string:
    raise RuntimeError("プロンプトファイルの読み込みに失敗しました。")
PROMPT = PromptTemplate(template=prompt_template_string,
                        input_variables=["scores_text", "context"])


# --- Flaskルーティング ---
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    password = data.get('password')
    if password == ADMIN_PASSWORD:
        return jsonify({"success": True, "role": "admin"})
    elif password == USER_PASSWORD:
        return jsonify({"success": True, "role": "user"})
    else:
        return jsonify({"success": False}), 401


def cleanup_old_charts():
    """staticフォルダ内の古いチャート画像を削除する"""
    for filename in os.listdir(STATIC_DIR):
        if filename.startswith('chart_') and filename.endswith('.png'):
            try:
                os.remove(os.path.join(STATIC_DIR, filename))
            except OSError as e:
                print(f"古いグラフの削除に失敗: {e}")


@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not llm or not retriever:
        return jsonify({"error": "サーバーが正しく初期化されていません。"}), 500

    # 前回のレポート生成時に作成された画像を削除
    cleanup_old_charts()

    scores = request.json
    if not scores or len(scores) != len(RADAR_CHART_METRICS):
        return jsonify({"error": f"{len(RADAR_CHART_METRICS)}指標のスコアが必要です。"}), 400

    chart_url = create_radar_chart(scores)

    # LLMへの入力を準備
    scores_text = "\n".join(
        [f"- {name}: {value}" for name, value in scores.items()])
    sorted_scores = sorted(scores.items(), key=lambda item: int(item[1]))
    query = f"{sorted_scores[-1][0]}が高く、{sorted_scores[0][0]}が低い人の特徴"
    context_docs = retriever.invoke(query)
    context = "\n\n".join([doc.page_content for doc in context_docs])
    sources = list(
        set([
            os.path.basename(doc.metadata.get('source', '不明'))
            for doc in context_docs
        ]))

    # LLMチェーンを実行してレポートを生成
    llm_chain = LLMChain(llm=llm, prompt=PROMPT)
    result = llm_chain.invoke({"scores_text": scores_text, "context": context})
    report_text = result.get("text", "レポートの生成に失敗しました。")
    html_report = markdown.markdown(report_text, extensions=['tables'])
    return jsonify({
        "report": html_report,
        "chart_url": chart_url,
        "sources": sources
    })


@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    if not worksheet:
        return jsonify({"error": "サーバー側でデータベースに接続できていません。"}), 500
    
    data = request.json
    report_html = data.get('report')
    rating = data.get('rating')
    comment = data.get('comment')

    if not report_html:
        return jsonify({"error": "レポート内容は必須です。"}), 400

    # 日本時間でタイムスタンプを生成
    timestamp = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
    
    sources = data.get('sources', '') # 'sources'キーでデータを受け取る（なければ空文字）

    # スプレッドシートに追記する行データを作成
    new_row = [timestamp, report_html, rating, comment, sources] # sources を末尾に追加
    
    try:
        worksheet.append_row(new_row)
        return jsonify({"success": True, "message": "フィードバックを記録しました。"})
    except Exception as e:
        print(f"スプレッドシートへの書き込みエラー: {e}")
        return jsonify({"error": "フィードバックの記録に失敗しました。"}), 500


def run_app():
    # Cloud Runから渡されるPORT環境変数を読み取り、なければ8080を使う
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    run_app()