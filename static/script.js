document.addEventListener('DOMContentLoaded', () => {
    // --- 要素の取得 ---
    const loginScreen = document.getElementById('login-screen');
    const mainScreen = document.getElementById('main-screen');
    const passwordInput = document.getElementById('password');
    const loginButton = document.getElementById('login-button');
    const loginError = document.getElementById('login-error');

    const scoresGrid = document.querySelector('.scores-grid');
    const generateButton = document.getElementById('generate-button');
    const resetButton = document.getElementById('reset-button');
    const loadingDiv = document.getElementById('loading');
    const reportHeader = document.getElementById('report-header');
    const reportOutput = document.getElementById('report-output');

    const adminArea = document.getElementById('admin-area');
    const submitFeedbackButton = document.getElementById('submit-feedback-button');
    const feedbackText = document.getElementById('feedback-text');
    const feedbackSuccess = document.getElementById('feedback-success');

    const indicators = [
        "会話性", "交流性", "幸福性", "表出性",
        "共感性", "尊重性", "融和性", "開示性",
        "創造性", "自立性", "感受性", "充実性"
    ];

    // --- ログイン処理 ---
    loginButton.addEventListener('click', async () => {
        const password = passwordInput.value;
        loginButton.disabled = true;
        loginError.textContent = '';
        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: password })
            });
            const data = await response.json();
            if (data.success) {
                loginScreen.style.display = 'none';
                mainScreen.style.display = 'block';
                if (data.role === 'admin') {
                    document.body.classList.add('admin-view');
                }
            } else {
                loginError.textContent = "パスワードが間違っています。";
            }
        } catch (error) {
            loginError.textContent = "認証中にエラーが発生しました。";
        } finally {
            loginButton.disabled = false;
        }
    });

    // --- 12指標の入力欄を動的に生成 ---
    indicators.forEach(name => {
        const group = document.createElement('div');
        group.className = 'score-input-group';
        const label = document.createElement('label');
        label.textContent = name;
        label.htmlFor = `score-${name}`;
        const input = document.createElement('input');
        input.type = 'number';
        input.id = `score-${name}`;
        input.name = name;
        input.placeholder = "0-40";
        input.min = 0;
        input.max = 40;
        input.step = 1; // 整数のみ入力可能にする
        group.appendChild(label);
        group.appendChild(input);
        scoresGrid.appendChild(group);
    });

    // --- リセットボタンの機能 ---
    resetButton.addEventListener('click', () => {
        indicators.forEach(name => {
            document.getElementById(`score-${name}`).value = '';
        });
        reportHeader.innerHTML = '';
        reportOutput.innerHTML = '';
        adminArea.style.display = 'none';
    });

    // --- ヘッダー（グラフと表）を表示する関数 ---
    function displayReportHeader(scores, chartUrl) {
        let tableHTML = '<table>';
        for (let i = 0; i < 3; i++) {
            tableHTML += '<tr>';
            for (let j = 0; j < 4; j++) {
                const index = i * 4 + j;
                if (index < indicators.length) {
                    const indicator = indicators[index];
                    tableHTML += `<td>
                                    <div class="indicator-name">${indicator}</div>
                                    <div class="indicator-score">${scores[indicator]}</div>
                                  </td>`;
                }
            }
            tableHTML += '</tr>';
        }
        tableHTML += '</table>';
        reportHeader.innerHTML = `
            <h2>診断結果サマリー</h2>
            <div class="summary-grid">
                <div class="chart-container">
                    <img src="${chartUrl}?t=${new Date().getTime()}" alt="レーダーチャート">
                </div>
                <div class="table-container">
                    ${tableHTML}
                </div>
            </div>
        `;
    }

    // --- レポート生成処理 ---
    generateButton.addEventListener('click', async () => {
        const scores = {};
        let allFilled = true;
        let validationError = '';

        indicators.forEach(name => {
            const input = document.getElementById(`score-${name}`);
            if (input.value === '') {
                allFilled = false;
            }
            const value = Number(input.value);
            if (!Number.isInteger(value) || value < 0 || value > 40) {
                validationError = '0から40までの整数を入力してください。';
            }
            scores[name] = input.value;
        });

        if (!allFilled) {
            alert('すべての指標を入力してください。');
            return;
        }
        if (validationError) {
            alert(validationError);
            return;
        }

        generateButton.disabled = true;
        resetButton.disabled = true;
        loadingDiv.style.display = 'block';
        reportOutput.textContent = '';
        reportHeader.innerHTML = '';
        adminArea.style.display = 'none'; 

        try {
            const response = await fetch('/generate-report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(scores),
            });
            if (!response.ok) throw new Error(`サーバーエラー: ${response.status}`);
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            displayReportHeader(scores, data.chart_url);
            reportOutput.innerHTML = data.report;

            const sourceList = document.getElementById('source-list');
            sourceList.innerHTML = '';
            if (data.sources && data.sources.length > 0) {
                data.sources.forEach(sourceName => {
                    const li = document.createElement('li');
                    li.textContent = sourceName;
                    sourceList.appendChild(li);
                });
            }

            if(document.body.classList.contains('admin-view')) {
                adminArea.style.display = 'block';
            }

        } catch (error) {
            reportOutput.textContent = `エラーが発生しました: ${error.message}`;
        } finally {
            generateButton.disabled = false;
            resetButton.disabled = false;
            loadingDiv.style.display = 'none';
        }
    });

    // --- フィードバック送信処理 ---
        submitFeedbackButton.addEventListener('click', async () => {
        // 選択されている評価（★）を取得する（選択されていなくてもOK）
        const ratingInput = document.querySelector('input[name="feedback-rating"]:checked');
        const rating = ratingInput ? ratingInput.value : ''; // 選択されていればその値を、なければ空文字を送信
        const comment = feedbackText.value;

        // 参照ナレッジのリストを取得し、カンマ区切りの一つの文字列に変換する
        const sources = Array.from(document.querySelectorAll('#source-list li'))
                             .map(li => li.textContent)
                             .join(', ');

        // Python側が期待するデータ形式に合わせる
        const feedbackData = {
            report: document.getElementById('report-output').innerHTML,
            rating: rating,
            comment: comment,
            sources: sources // 参照ナレッジのデータを追加
        };

        try {
            const response = await fetch('/submit-feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(feedbackData)
            });
        
            // エラーレスポンスの本文を取得して表示する改善
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '不明なエラー');
            }

            const data = await response.json();
            if (data.success) {
                feedbackSuccess.textContent = data.message;
                feedbackSuccess.style.display = 'block';
                feedbackText.value = '';
                // もし評価が選択されていた場合のみ、その選択をリセットする
                if (ratingInput) {
                    ratingInput.checked = false;
                }
                setTimeout(() => {
                    feedbackSuccess.style.display = 'none';
                }, 3000);
            } else {
                // サーバーからの具体的なエラーメッセージを表示
                alert(`エラー: ${data.error}`);
            }
        } catch (error) {
            alert(`フィードバックの送信に失敗しました: ${error.message}`);
        }
    });    
});

// script.jsの一番下に追記
// --- ログアウト処理 ---
const logoutButton = document.getElementById('logout-button');
logoutButton.addEventListener('click', () => {
    location.reload();
});