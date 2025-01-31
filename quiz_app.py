import streamlit as st
import pandas as pd
import sqlite3
import re

# データベースの初期化
def initialize_database():
    conn = sqlite3.connect('quiz_app.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            options TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            explanation TEXT,
            note TEXT,
            flagged INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            question_id INTEGER,
            correct INTEGER,
            FOREIGN KEY (question_id) REFERENCES questions (id)
        )
    ''')
    conn.commit()
    conn.close()

# 問題をデータベースにインポート
def import_questions_from_csv(file):
    conn = sqlite3.connect('quiz_app.db')
    df = pd.read_csv(file, encoding='cp932')
    df.applymap(lambda x: re.sub(r"\s+", "", x) if isinstance(x, str) else x)
    df.to_sql('questions', conn, if_exists='append', index=False)
    conn.close()

# 問題をデータベースからエクスポート
def export_questions_to_csv():
    conn = sqlite3.connect('quiz_app.db')
    # SQLクエリを使用してデータを読み込む
    query = 'SELECT * FROM  questions'
    df = pd.read_sql_query(query, conn)
    # データをCSVファイルにエクスポート
    csv = df.to_csv(index=False,encoding='cp932')
    # CSVファイルをダウンロード可能にする
    st.download_button(
        label="CSVでダウンロード",
        data=csv,
        file_name='output.csv',
        mime='text/csv',
    )
    # 接続を閉じる
    conn.close()

# 条件に応じた問題を取得（ランダム一問）
def fetch_random_question(flagged_only=False, incorrect_only=False):
    conn = sqlite3.connect('quiz_app.db')
    query = 'SELECT * FROM questions'
    conditions = []
    if flagged_only:
        conditions.append('flagged = 1')
    if incorrect_only:
        conditions.append('id IN (SELECT question_id FROM results WHERE correct = 0)')
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY RANDOM() LIMIT 1'
    question = pd.read_sql(query, conn)
    conn.close()
    return question

# 解答結果を保存（正解の場合は間違えたリストから削除）
def save_result(question_id, correct):
    conn = sqlite3.connect('quiz_app.db')
    cursor = conn.cursor()
    # 正解の場合は「間違えた問題」リストから削除
    if correct:
        cursor.execute('DELETE FROM results WHERE question_id = ?', (question_id,))
    else:
        cursor.execute('INSERT OR REPLACE INTO results (question_id, correct) VALUES (?, ?)', (question_id, correct))
    conn.commit()
    conn.close()

# 問題のフラグを更新
def update_flag(question_id, flagged):
    conn = sqlite3.connect('quiz_app.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE questions SET flagged = ? WHERE id = ?', (flagged, question_id))
    conn.commit()
    conn.close()

# セッションの状態をリセット
def reset_session():
    st.session_state['current_question'] = None
    st.session_state['user_answers'] = []
    st.session_state['is_correct'] = None
    st.session_state['show_explanation'] = False

# Streamlitアプリケーション
def main():
    st.title('Google Cloud Professional Data Engineer 問題集')

    # データベース初期化
    initialize_database()

    # 初期化
    if 'current_question' not in st.session_state:
        reset_session()

    # サイドバー
    st.sidebar.header('メニュー')
    menu = st.sidebar.selectbox('選択してください', ['問題を解く', '間違えた/フラグ付き問題に挑戦', 'CSVから問題をインポート','問題集を出力'])

    if menu == 'CSVから問題をインポート':
        st.header('CSVから問題をインポート')
        uploaded_file = st.file_uploader('CSVファイルを選択してください', type='csv')
        if uploaded_file is not None:
            try:
                import_questions_from_csv(uploaded_file)
                st.success('問題がインポートされました')
            except Exception as e:
                st.error(f'エラーが発生しました: {e}')

    elif menu == '問題を解く':
        # st.header('問題を解く')

        if st.button('次の問題を取得'):
            reset_session()
            question = fetch_random_question()
            if not question.empty:
                st.session_state['current_question'] = question.iloc[0].to_dict()

        question_data = st.session_state['current_question']
        if question_data:
            st.text(question_data['question'])
            # st.subheader(question_data['question'])
            options = question_data['options'].split(';')
            correct_answers = question_data['correct_answer'].split(';')

            if len(correct_answers) == 1:
                st.session_state['user_answers'] = [st.radio('回答を選択してください', options, key='radio')]
            else:
                st.session_state['user_answers'] = [option for option in options if st.checkbox(option, key=option)]

            if st.button('回答する'):
                user_answers = st.session_state['user_answers']
                st.session_state['is_correct'] = set(user_answers) == set(correct_answers)
                st.session_state['show_explanation'] = True
                save_result(question_data['id'], int(st.session_state['is_correct']))

            if st.session_state['show_explanation']:
                if st.session_state['is_correct']:
                    st.success('正解です！')
                else:
                    st.error('不正解です')
                st.info(f"解説: {question_data['explanation']}")
                if question_data['note']:
                    st.warning(f"備考: {question_data['note']}")
                if st.checkbox('後で復習する', key='flag'):
                    update_flag(question_data['id'], 1)
        else:
            st.info('「次の問題を取得」をクリックしてください。')

    elif menu == '間違えた/フラグ付き問題に挑戦':
        # st.header('間違えた/フラグ付き問題に挑戦')

        flagged_only = st.sidebar.checkbox('フラグ付き問題だけ表示')
        incorrect_only = st.sidebar.checkbox('間違えた問題だけ表示')

        if st.button('問題を取得'):
            reset_session()
            question = fetch_random_question(flagged_only=flagged_only, incorrect_only=incorrect_only)
            if not question.empty:
                st.session_state['current_question'] = question.iloc[0].to_dict()

        question_data = st.session_state['current_question']
        if question_data:
            st.text(question_data['question'])
            # st.subheader(question_data['question'])
            options = question_data['options'].split(';')
            correct_answers = question_data['correct_answer'].split(';')

            if len(correct_answers) == 1:
                st.session_state['user_answers'] = [st.radio('回答を選択してください', options, key='radio')]
            else:
                st.session_state['user_answers'] = [option for option in options if st.checkbox(option, key=option)]

            if st.button('回答する'):
                user_answers = st.session_state['user_answers']
                st.session_state['is_correct'] = set(user_answers) == set(correct_answers)
                st.session_state['show_explanation'] = True
                save_result(question_data['id'], int(st.session_state['is_correct']))

            if st.session_state['show_explanation']:
                if st.session_state['is_correct']:
                    st.success('正解です！')
                else:
                    st.error(f'不正解です、正解は{correct_answers}')
                st.info(f"解説: {question_data['explanation']}")
                if question_data['note']:
                    st.warning(f"備考: {question_data['note']}")
                if st.checkbox('後で復習する', key='flag'):
                    update_flag(question_data['id'], 1)
        else:
            st.info('条件に一致する問題がありません。')

    elif menu == '問題集を出力':
        export_questions_to_csv()
        # st.success('csvファイルがダウンロードされました。')

if __name__ == '__main__':
    main()
