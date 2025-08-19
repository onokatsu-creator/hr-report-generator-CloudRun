import os
import uuid
import numpy as np
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


# --- 初期設定 ---
load_dotenv()
app = Flask(__name__)

# --- Secretsからパスワードを読み込む ---
USER_PASSWORD = os.getenv("USER_PASSWORD")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# --- Google Sheetsの設定 ---
try:
    # 環境変数から設定を読み込む
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
    SHEET_NAME = os.getenv("SHEET_NAME", "FB")
    SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")

    # Google Sheets APIのスコープを設定
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)
    print("--- Google Sheetsへの接続完了 ---")
except Exception as e:
    print(f"エラー: Google Sheetsへの接続に失敗しました。 {e}")
    worksheet = None

# 日本語フォントのパスを指定
FONT_PATH = 'fonts/MPLUS1p-Regular.ttf'
if os.path.exists(FONT_PATH):
    font_prop = fm.FontProperties(fname=FONT_PATH)
else:
    font_prop = None


def create_radar_chart(scores_dict):
    desired_order = [
        "充実性", "会話性", "交流性", "幸福性", "表出性", "共感性", "尊重性", "融和性", "開示性", "創造性",
        "自立性", "感受性"
    ]
    values = [float(scores_dict.get(k, 0)) for k in desired_order]
    avg_values = [22] * len(desired_order)
    values_plot = values + [values[0]]
    avg_values_plot = avg_values + [avg_values[0]]
    angles = np.linspace(0, 2 * np.pi, len(desired_order),
                         endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 40)
    ax.set_rgrids([10, 20, 30, 40], angle=0)
    ax.set_xticks(angles[:-1])
    if font_prop:
        ax.set_xticklabels(desired_order, fontproperties=font_prop, size=12)
    else:
        ax.set_xticklabels(desired_order, size=12)
    ax.plot(angles, values_plot, color='red', linewidth=2.5)
    ax.fill(angles, values_plot, 'red', alpha=0.25)
    ax.plot(angles, avg_values_plot, color='blue', linewidth=1, linestyle='-')
    filename = f"chart_{uuid.uuid4()}.png"
    filepath = os.path.join("static", filename)
    plt.savefig(filepath, bbox_inches='tight', pad_inches=0.2)
    plt.close(fig)
    return f"/static/{filename}"


def load_prompt(template_name="default_report.txt"):
    try:
        with open(os.path.join("prompts", template_name),
                  "r",
                  encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# --- LLMとベクトルDBの準備 ---
try:
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7)
    embeddings = OpenAIEmbeddings()
    vector_db = FAISS.load_local("vectorstore/db_faiss",
                                 embeddings,
                                 allow_dangerous_deserialization=True)
    retriever = vector_db.as_retriever(search_kwargs={'k': 5})
    print("--- LLMとベクトルデータベースの読み込み完了 ---")
except Exception as e:
    print(f"エラー: 初期設定中に問題が発生しました。 {e}")
    llm = None

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


@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not llm:
        return jsonify({"error": "サーバーが正しく初期化されていません。"}), 500

    # --- ★★★ 古いグラフ画像を自動削除する処理を追加 ★★★ ---
    static_folder = 'static'
    for filename in os.listdir(static_folder):
        if filename.startswith('chart_') and filename.endswith('.png'):
            try:
                os.remove(os.path.join(static_folder, filename))
            except Exception as e:
                print(f"古いグラフの削除に失敗: {e}")
    # --- ここまで追加 ---

    import markdown
    scores = request.json
    if not scores or len(scores) != 12:
        return jsonify({"error": "12指標のスコアが必要です。"}), 400

    chart_url = create_radar_chart(scores)
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

    # タイムゾーンを日本時間に設定
    jst = pytz.timezone('Asia/Tokyo')
    timestamp = datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')
    
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
    app.run(host='0.0.0.0', port=8080)


if __name__ == '__main__':
    run_app()