const views = {
  home: document.getElementById("home-view"),
  test: document.getElementById("test-view"),
  result: document.getElementById("result-view"),
  batch: document.getElementById("batch-view"),
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
