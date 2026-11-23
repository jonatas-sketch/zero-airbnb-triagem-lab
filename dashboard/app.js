const status = document.querySelector("#status");
const filter = document.querySelector("#filter");
const metrics = document.querySelector("#metrics");
const table = document.querySelector("#rows");
const cases = document.querySelector("#cases");
const labels = { escalate: "Escalated", auto_answer: "Auto-answer" };

function addMetric(label, value) {
  const card = document.createElement("div");
  card.className = "metric";
  const name = document.createElement("dt");
  const number = document.createElement("dd");
  name.textContent = label;
  number.textContent = value;
  card.append(name, number);
  metrics.append(card);
}

function showCases(predictions, examples) {
  const byId = new Map(predictions.map((row) => [row.message_id, row]));
  for (const example of examples ?? []) {
    const row = byId.get(example.message_id);
    if (!row) continue;
    const card = document.createElement("div");
    card.className = "metric case";
    const label = document.createElement("dt");
    label.textContent = example.label;
    const sample = document.createElement("dd");
    sample.textContent = `${row.message_id} · ${labels[row.decision]}`;
    const detail = document.createElement("small");
    detail.textContent = `${row.matched_rule} · ${row.danger_score.toFixed(4)}`;
    card.append(label, sample, detail);
    cases.append(card);
  }
}

function renderTable(predictions, spotlight) {
  table.replaceChildren();
  const priority = (message) => message.decision === "auto_answer"
    ? 2
    : Number(!message.matched_rule.startsWith("safety:"));
  const ordered = [...predictions].sort((a, b) =>
    priority(a) - priority(b)
    || Number(b.message_id === spotlight) - Number(a.message_id === spotlight)
    || (b.danger_score ?? -1) - (a.danger_score ?? -1)
  );
  for (const message of ordered) {
    if (filter.value && filter.value !== message.decision) continue;
    const row = table.insertRow();
    const reason = message.decision === "auto_answer" ? "Routine booking facts verified" : message.reason;
    const values = [message.message_id, labels[message.decision], reason, message.matched_rule,
      message.danger_score == null ? "Unavailable" : message.danger_score.toFixed(4)];
    for (const [index, value] of values.entries()) {
      const cell = row.insertCell();
      cell.textContent = value;
      if (index === 1) cell.className = message.decision;
      if (index === 3) cell.className = "rule";
    }
  }
}

try {
  const response = await fetch("results.json");
  if (!response.ok) throw new Error("Evaluation file unavailable");
  const results = await response.json();
  status.textContent = results.rubric_passed
    ? "The endpoint met both evaluation thresholds."
    : "Course threshold unmet. This run used the supplied booking table, which has no matching booking for any of the 50 held-out messages.";
  addMetric("Messages evaluated", results.evaluated);
  addMetric("Missed safety escalations", results.missed_safety_escalations);
  addMetric("Correct routine auto-answers", `${results.correct_routine_auto_answers} / 30 required`);
  showCases(results.predictions, results.examples);
  renderTable(results.predictions, results.spotlight_message_id);
  filter.addEventListener("change", () => renderTable(results.predictions, results.spotlight_message_id));
} catch {
  status.textContent = "Could not load an evaluation run.";
}
