import os
import shutil
import glob
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# .envファイルから環境変数を読み込む
load_dotenv()

# --- 定数設定 ---
DATA_PATH = "data"
DB_FAISS_PATH = "vectorstore/db_faiss"


def create_vector_db():
    """
    dataフォルダ内のPDFを読み込み、ベクトル化してFAISSに保存する関数
    """
    if os.path.exists(DB_FAISS_PATH):
        print(f"--- 古いデータベース '{DB_FAISS_PATH}' を削除します ---")
        shutil.rmtree(DB_FAISS_PATH)
        print("--- 古いデータベースを削除しました ---")

    print("--- ベクトルデータベースの作成を開始します ---")

    # 1-A. globを使って、dataフォルダからPDFのファイルパスをリストアップする
    pdf_files = glob.glob(os.path.join(DATA_PATH, '*.pdf'))

    if not pdf_files:
        print(f"エラー: {DATA_PATH} フォルダにPDFファイルが見つかりません。")
        return

    print(f"プログラムが、{len(pdf_files)}個のPDFパスを特定しました。")

    # 1-B. 各PDFファイルをPyPDFLoaderで個別に読み込み、リストに格納する
    all_documents = []
    for file_path in pdf_files:
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            all_documents.extend(documents)
        except Exception as e:
            print(f"エラー: {file_path} の読み込みに失敗しました。理由: {e}")

    # ★★★ メッセージを分かりやすく修正 ★★★
    print(
        f"--- {len(pdf_files)}個のPDFファイルから、合計{len(all_documents)}ページ分のドキュメントを読み込みました ---"
    )

    # 2. ドキュメントをチャンク（小さな塊）に分割する
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000,
                                                   chunk_overlap=200)
    texts = text_splitter.split_documents(all_documents)
    print(f"ドキュメントを{len(texts)}個のチャンクに分割しました。")

    # 3. チャンクをベクトル化し、FAISSベクトルストアを作成する
    embeddings = OpenAIEmbeddings()
    db = FAISS.from_documents(texts, embeddings)

    # 4. 作成したベクトルストアをローカルに保存する
    db.save_local(DB_FAISS_PATH)
    print(f"--- ベクトルデータベースを '{DB_FAISS_PATH}' に保存しました ---")


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("エラー: OpenAIのAPIキーが設定されていません。")
    else:
        create_vector_db()
