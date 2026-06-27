const views = {
  home: document.getElementById("home-view"),
  test: document.getElementById("test-view"),
  result: document.getElementById("result-view"),
  "cat-test": document.getElementById("cat-test-view"),
  "cat-result": document.getElementById("cat-result-view"),
  batch: document.getElementById("batch-view"),
  "real-batch": document.getElementById("real-batch-view"),
  "real-batch-result": document.getElementById("real-batch-result-view"),
  "text": document.getElementById("text-view"),
  "text-result": document.getElementById("text-result-view"),
};

let sessionId = null;
let currentQuestion = null;
let totalQuestions = 0;

function showView(name) {
  Object.entries(views).forEach(([key, element]) => {
    element.classList.toggle("hidden", key !== name);
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "请求失败");
  }
  return response.json();
}

function renderQuestion(question) {
  currentQuestion = question;
  totalQuestions = question.total_questions;
  document.getElementById("progress-text").textContent =
    `第 ${question.question_index + 1} / ${question.total_questions} 题`;
  document.getElementById("progress-fill").style.width =
    `${((question.question_index + 1) / question.total_questions) * 100}%`;
  document.getElementById("question-level").textContent = question.level;
  document.getElementById("question-word").textContent = question.word;
  document.getElementById("question-definition").textContent =
    question.definition || "（暂无释义，请根据单词本身判断）";
}

function renderResult(result) {
  document.getElementById("result-summary").textContent = result.summary;
  document.getElementById("point-estimate").textContent = result.point_estimate;
  document.getElementById("lower-bound").textContent = result.lower_bound;
  document.getElementById("upper-bound").textContent = result.upper_bound;

  const tbody = document.querySelector("#breakdown-table tbody");
  tbody.innerHTML = "";
  result.level_breakdown.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>L${item.level}</td>
      <td>${item.rank_start}-${item.rank_end}</td>
      <td>${(item.recognition_rate * 100).toFixed(1)}%</td>
      <td>${item.known_words} / ${item.total_words}</td>
    `;
    tbody.appendChild(row);
  });
  showView("result");
}

async function startTest() {
  const data = await api("/api/test/start", { method: "POST" });
  sessionId = data.session_id;
  renderQuestion(data.first_question);
  showView("test");
}

async function submitAnswer(response) {
  if (!currentQuestion) return;

  const data = await api(`/api/test/${sessionId}/answer`, {
    method: "POST",
    body: JSON.stringify({
      word_id: currentQuestion.word_id,
      response,
    }),
  });

  if (data.finished) {
    const result = await api(`/api/test/${sessionId}/result`);
    renderResult(result);
    return;
  }

  renderQuestion(data.next_question);
}

async function loadBatchResults() {
  const data = await api("/api/batch/estimate/default");
  const tbody = document.querySelector("#batch-table tbody");
  tbody.innerHTML = "";

  data.results.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.profile}</td>
      <td>${item.point_estimate}</td>
      <td>${item.lower_bound} - ${item.upper_bound}</td>
      <td>${Math.round(item.confidence_level * 100)}%</td>
    `;
    tbody.appendChild(row);
  });

  showView("batch");
}

document.getElementById("start-btn").addEventListener("click", () => {
  startTest().catch((error) => alert(error.message));
});

document.getElementById("batch-btn").addEventListener("click", () => {
  loadBatchResults().catch((error) => alert(error.message));
});

document.getElementById("restart-btn").addEventListener("click", () => {
  sessionId = null;
  currentQuestion = null;
  showView("home");
});

document.getElementById("back-home-btn").addEventListener("click", () => {
  showView("home");
});

document.querySelectorAll(".answer-btn").forEach((button) => {
  button.addEventListener("click", () => {
    submitAnswer(button.dataset.response).catch((error) => alert(error.message));
  });
});

document.getElementById("test-exit-btn").addEventListener("click", () => {
  const confirmed = window.confirm("确定要退出当前测试吗？已答的题目将不会保存。");
  if (!confirmed) return;
  sessionId = null;
  currentQuestion = null;
  showView("home");
});

function parseBatchInput(text) {
  const answers = [];
  const lines = text.split("\n").map((l) => l.trim()).filter((l) => l.length > 0);

  for (const line of lines) {
    let known = false;
    let word = line;

    if (line.startsWith("+")) {
      known = true;
      word = line.slice(1).trim();
    } else if (line.startsWith("-")) {
      known = false;
      word = line.slice(1).trim();
    } else {
      continue;
    }

    if (word) {
      answers.push({ word, known });
    }
  }

  return answers;
}

function renderRealBatchResult(result) {
  document.getElementById("real-batch-summary").textContent = result.summary;
  document.getElementById("real-point-estimate").textContent = result.point_estimate;
  document.getElementById("real-lower-bound").textContent = result.lower_bound;
  document.getElementById("real-upper-bound").textContent = result.upper_bound;

  const tbody = document.querySelector("#real-batch-breakdown-table tbody");
  tbody.innerHTML = "";
  result.level_breakdown.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>L${item.level}</td>
      <td>${item.rank_start}-${item.rank_end}</td>
      <td>${item.sampled_count}</td>
      <td>${item.known_count}</td>
      <td>${(item.recognition_rate * 100).toFixed(1)}%</td>
      <td>${item.estimated_known_words} / ${item.total_words}</td>
    `;
    tbody.appendChild(row);

    if (item.unknown_words && item.unknown_words.length > 0) {
      const detailRow = document.createElement("tr");
      detailRow.className = "level-detail-row";
      const detailCell = document.createElement("td");
      detailCell.colSpan = 6;
      const tags = item.unknown_words.map(w => `<span class="word-tag unknown">${w}</span>`).join("");
      detailCell.innerHTML = `<span class="detail-label">不认识：</span>${tags}`;
      detailRow.appendChild(detailCell);
      tbody.appendChild(detailRow);
    }
  });

  const unmatchedSection = document.getElementById("unmatched-section");
  const unmatchedWords = document.getElementById("unmatched-words");
  if (result.unmatched_words && result.unmatched_words.length > 0) {
    unmatchedSection.classList.remove("hidden");
    unmatchedWords.textContent = result.unmatched_words.join(", ");
  } else {
    unmatchedSection.classList.add("hidden");
  }

  showView("real-batch-result");
}

async function submitRealBatch() {
  const input = document.getElementById("batch-input").value;
  const answers = parseBatchInput(input);

  if (answers.length === 0) {
    alert("请输入有效的单词列表，每行一个，前缀 + 表示认识，- 表示不认识");
    return;
  }

  try {
    const data = await api("/api/batch/estimate-from-words", {
      method: "POST",
      body: JSON.stringify({ answers, algorithm: "stratified" }),
    });
    renderRealBatchResult(data);
  } catch (error) {
    alert(error.message);
  }
}

document.getElementById("real-batch-btn").addEventListener("click", () => {
  showView("real-batch");
});

document.getElementById("real-batch-back-btn").addEventListener("click", () => {
  showView("home");
});

document.getElementById("real-batch-submit-btn").addEventListener("click", () => {
  submitRealBatch();
});

document.getElementById("real-batch-restart-btn").addEventListener("click", () => {
  showView("real-batch");
});

// ============== 文章分析 ==============

const LEVEL_RANGES = [
  [1, 1, 1000],
  [2, 1001, 3000],
  [3, 3001, 6000],
  [4, 6001, 10000],
  [5, 10001, 20000],
];

function getLevelRange(level) {
  const range = LEVEL_RANGES.find(r => r[0] === level);
  return range ? `${range[1]}-${range[2]}` : "-";
}

function renderTextResult(data) {
  document.getElementById("text-stats-summary").textContent =
    `文档共 ${data.total_words} 个不同单词，其中 ${data.matched_words} 个可识别词频等级`;

  const est = data.vocab_estimate;
  document.getElementById("text-point-estimate").textContent = est.point_estimate;
  document.getElementById("text-lower-bound").textContent = est.lower_bound;
  document.getElementById("text-upper-bound").textContent = est.upper_bound;
  document.getElementById("text-explanation").textContent = est.explanation;

  showView("text-result");
}

async function submitTextAnalysis() {
  const text = document.getElementById("text-input").value.trim();
  if (!text) {
    alert("请输入要分析的英文文档");
    return;
  }
  const confidence = parseInt(document.getElementById("text-confidence").value) / 100;
  
  try {
    const data = await api("/api/text/analyze", {
      method: "POST",
      body: JSON.stringify({ text, min_recognition_rate: confidence }),
    });
    renderTextResult(data);
  } catch (error) {
    alert(error.message);
  }
}

document.getElementById("text-btn").addEventListener("click", () => {
  showView("text");
});

document.getElementById("text-submit-btn").addEventListener("click", () => {
  submitTextAnalysis();
});

document.getElementById("text-back-btn").addEventListener("click", () => {
  showView("home");
});

document.getElementById("text-confidence").addEventListener("input", (e) => {
  document.getElementById("text-confidence-value").textContent = `${e.target.value}%`;
});

document.getElementById("text-restart-btn").addEventListener("click", () => {
  document.getElementById("text-input").value = "";
  document.getElementById("text-confidence").value = 85;
  document.getElementById("text-confidence-value").textContent = "85%";
  showView("text");
});

// ============== IRT-CAT 自适应测试 ==============

let catSessionId = null;
let catCurrentQuestion = null;
let catItemsAnswered = 0;
const CAT_MAX_ITEMS = 25;

function renderCatQuestion(question, itemsAnswered) {
  catCurrentQuestion = question;
  catItemsAnswered = itemsAnswered;
  const progress = Math.min(itemsAnswered / CAT_MAX_ITEMS, 1);
  document.getElementById("cat-progress-text").textContent =
    `第 ${itemsAnswered} / ${CAT_MAX_ITEMS} 题 (自适应)`;
  document.getElementById("cat-progress-fill").style.width = `${progress * 100}%`;
  document.getElementById("cat-question-word").textContent = question.word;
  document.getElementById("cat-question-definition").textContent =
    question.definition || "（暂无释义，请根据单词本身判断）";
}

function renderCatResult(result) {
  document.getElementById("cat-result-summary").textContent = result.summary;
  document.getElementById("cat-point-estimate").textContent = result.point_estimate;
  document.getElementById("cat-lower-bound").textContent = result.lower_bound;
  document.getElementById("cat-upper-bound").textContent = result.upper_bound;
  document.getElementById("cat-items-answered").textContent = result.items_answered;
  document.getElementById("cat-theta").textContent = result.theta.toFixed(3);
  document.getElementById("cat-theta-se").textContent = result.theta_se.toFixed(3);
  showView("cat-result");
}

async function startCatTest() {
  try {
    const data = await api("/api/cat/start", { method: "POST" });
    catSessionId = data.session_id;
    renderCatQuestion(data.first_question, 1);
    showView("cat-test");
  } catch (error) {
    alert(error.message);
  }
}

async function submitCatAnswer(response) {
  if (!catCurrentQuestion) return;

  try {
    const data = await api(`/api/cat/${catSessionId}/answer`, {
      method: "POST",
      body: JSON.stringify({
        word_id: catCurrentQuestion.word_id,
        response,
      }),
    });

    if (data.finished) {
      const result = await api(`/api/cat/${catSessionId}/result`);
      renderCatResult(result);
      return;
    }

    if (data.next_question) {
      renderCatQuestion(data.next_question, data.status.items_answered + 1);
    }
  } catch (error) {
    alert(error.message);
  }
}

document.getElementById("cat-start-btn").addEventListener("click", () => {
  startCatTest();
});

document.querySelectorAll(".cat-answer-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const response = btn.dataset.response;
    submitCatAnswer(response);
  });
});

document.getElementById("cat-exit-btn").addEventListener("click", () => {
  if (confirm("确定要退出测试吗？")) {
    showView("home");
  }
});

document.getElementById("cat-restart-btn").addEventListener("click", () => {
  startCatTest();
});
