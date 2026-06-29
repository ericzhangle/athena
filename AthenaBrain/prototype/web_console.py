from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from athena_brain import CognitiveEngine


ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data"
DEFAULT_DATASET = "phase1_fruit_curriculum_test"


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Athena Brain Console</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; background: #0f172a; color: #e5e7eb; }
    header { padding: 18px 24px; background: #111827; border-bottom: 1px solid #334155; }
    h1 { margin: 0 0 6px; font-size: 22px; }
    main { display: grid; grid-template-columns: 280px 1fr; gap: 16px; padding: 16px; }
    section, aside { background: #111827; border: 1px solid #334155; border-radius: 10px; padding: 14px; }
    select, input, textarea, button { border-radius: 8px; border: 1px solid #475569; padding: 8px; background: #020617; color: #e5e7eb; }
    textarea { width: 100%; min-height: 120px; box-sizing: border-box; }
    button { cursor: pointer; background: #1d4ed8; border-color: #2563eb; }
    button:hover { background: #2563eb; }
    .concept { display: block; width: 100%; text-align: left; margin: 6px 0; background: #020617; }
    .concept.active { background: #1e40af; }
    .muted { color: #94a3b8; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    pre { white-space: pre-wrap; background: #020617; border-radius: 8px; padding: 10px; border: 1px solid #334155; }
    .pill { display: inline-block; padding: 3px 8px; margin: 2px; border-radius: 999px; background: #334155; }
    .row { margin-bottom: 10px; }
    .question-card { border: 1px solid #334155; border-radius: 8px; padding: 10px; margin: 8px 0; background: #020617; }
    .question-card input { width: 72%; }
    .danger { color: #fca5a5; }
    @media (max-width: 900px) { main { grid-template-columns: 1fr; } .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Athena Brain Console</h1>
    <div class="muted">本地原型控制台：查看概念成长、证据状态，并进行无 LLM 的有限问答。</div>
  </header>
  <main>
    <aside>
      <div class="row">
        <label>数据集</label><br />
        <select id="dataset"></select>
      </div>
      <div class="row">
        <button onclick="loadAll()">刷新</button>
      </div>
      <h3>概念</h3>
      <div id="conceptList"></div>
    </aside>
    <section>
      <div class="grid">
        <div>
          <h2 id="conceptTitle">选择一个概念</h2>
          <div id="conceptMeta" class="muted"></div>
          <h3>描述</h3>
          <pre id="description"></pre>
        </div>
        <div>
          <h3>问 Athena</h3>
          <div class="row">
            <input id="question" style="width: 70%" value="描述一下 Fruit" />
            <button onclick="ask()">提问</button>
          </div>
          <pre id="answer"></pre>
          <div class="muted">无 LLM 模式支持：描述/特点/知道什么 + 概念名，例如“描述 Apple”“Fruit 有什么特点”。</div>
        </div>
      </div>
      <h3>Athena 的主动问题 / 好奇心</h3>
      <div class="muted">这些问题来自未成熟概念、未回答问题、属性变化、正反例边界和回答冲突。</div>
      <div id="curiosity"></div>
      <pre id="curiosityResult"></pre>
      <h3>输入知识文章</h3>
      <div class="muted">把一段知识交给 Athena。她会拆成 provisional claims，更新概念，并提出新的好奇问题。</div>
      <textarea id="knowledgeText" placeholder="在这里粘贴一段知识文章，例如关于水果、维生素C、膳食纤维的说明..."></textarea>
      <div class="row"><button onclick="ingestKnowledge()">吸收这段知识</button></div>
      <pre id="knowledgeResult"></pre>
      <h3>规则 / 推理</h3>
      <div class="muted">规则来自用户回答，推理属性会低置信度写入相关概念，并可关闭已能推断的问题。</div>
      <div id="rules"></div>
      <h3>研究循环 / Inquiry Loop</h3>
      <div class="muted">从当前好奇问题中自动选择问题，查询 mock reference provider，吸收回答，再继续生成新问题。</div>
      <div class="row">
        <input id="inquirySteps" style="width: 80px" value="10" />
        <button onclick="runInquiryLoop()">运行研究循环</button>
      </div>
      <pre id="inquiryResult"></pre>
      <h3>属性 / 抽象</h3>
      <div id="attributes"></div>
      <h3>关系</h3>
      <div id="relations"></div>
      <h3>正例 / 反例</h3>
      <div id="examples"></div>
      <h3>未解决问题</h3>
      <div id="questions"></div>
      <h3>原始 JSON</h3>
      <pre id="raw"></pre>
    </section>
  </main>
  <script>
    let currentDataset = "";
    let currentConcept = "";

    async function api(path, options) {
      const res = await fetch(path, options);
      if (!res.ok) throw new Error(await res.text());
      return await res.json();
    }

    async function loadDatasets() {
      const data = await api("/api/datasets");
      const select = document.getElementById("dataset");
      select.innerHTML = "";
      data.datasets.forEach(name => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        if (name === data.default_dataset) option.selected = true;
        select.appendChild(option);
      });
      currentDataset = select.value;
      select.onchange = () => { currentDataset = select.value; loadConcepts(); };
    }

    async function loadConcepts() {
      const data = await api(`/api/concepts?dataset=${encodeURIComponent(currentDataset)}`);
      const list = document.getElementById("conceptList");
      list.innerHTML = "";
      data.concepts.forEach(concept => {
        const button = document.createElement("button");
        button.className = "concept" + (concept.name === currentConcept ? " active" : "");
        button.textContent = `${concept.name} (${concept.maturity})`;
        button.onclick = () => loadConcept(concept.name);
        list.appendChild(button);
      });
      if (!currentConcept && data.concepts.length) loadConcept(data.concepts[0].name);
    }

    async function loadConcept(name) {
      currentConcept = name;
      const data = await api(`/api/concept?dataset=${encodeURIComponent(currentDataset)}&name=${encodeURIComponent(name)}`);
      document.getElementById("conceptTitle").textContent = data.concept.name;
      document.getElementById("conceptMeta").textContent = `maturity=${data.concept.maturity}, confidence=${data.concept.confidence}`;
      document.getElementById("description").textContent = data.description;
      document.getElementById("raw").textContent = JSON.stringify(data.concept, null, 2);
      renderPills("attributes", data.concept.attributes || [], item => `${item.name}: ${item.value} (${item.generalization_status}, ${item.confidence})`);
      renderPills("relations", data.concept.relations || [], item => `${data.concept.name} ${item.relation_type} ${item.target_concept} (${item.status})`);
      renderExamples(data.concept);
      renderPills("questions", data.concept.open_questions || [], item => item.question);
      await loadConcepts();
    }

    function renderPills(id, items, fn) {
      const node = document.getElementById(id);
      node.innerHTML = "";
      if (!items.length) { node.innerHTML = '<span class="muted">无</span>'; return; }
      items.forEach(item => {
        const span = document.createElement("span");
        span.className = "pill";
        span.textContent = fn(item);
        node.appendChild(span);
      });
    }

    function renderExamples(concept) {
      const node = document.getElementById("examples");
      const examples = (concept.examples || []).map(e => `正例: ${e.concept}`);
      const counterexamples = (concept.counterexamples || []).map(e => `反例: ${e.concept}`);
      const items = examples.concat(counterexamples);
      node.innerHTML = "";
      if (!items.length) { node.innerHTML = '<span class="muted">无</span>'; return; }
      items.forEach(text => {
        const span = document.createElement("span");
        span.className = "pill";
        span.textContent = text;
        node.appendChild(span);
      });
    }

    async function ask() {
      const question = document.getElementById("question").value;
      const data = await api("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset: currentDataset, question })
      });
      document.getElementById("answer").textContent = data.answer;
      if (data.concept) loadConcept(data.concept);
    }

    async function loadCuriosity() {
      const data = await api(`/api/curiosity?dataset=${encodeURIComponent(currentDataset)}`);
      const node = document.getElementById("curiosity");
      node.innerHTML = "";
      if (!data.questions.length) {
        node.innerHTML = '<span class="muted">Athena 暂时没有主动问题。</span>';
        return;
      }
      data.questions.forEach(q => {
        const card = document.createElement("div");
        card.className = "question-card";
        const conflict = q.status === "conflicted" || q.reason === "curiosity_answer_conflict";
        card.innerHTML = `
          <div><strong>${q.concept}</strong> <span class="${conflict ? "danger" : "muted"}">priority=${q.priority}, reason=${q.reason}</span></div>
          <div style="margin: 8px 0">${q.question}</div>
          <input id="answer-${q.question_id}" placeholder="在这里回答 Athena..." />
          <button onclick='answerCuriosity(${JSON.stringify(q)})'>回答</button>
        `;
        node.appendChild(card);
      });
    }

    async function answerCuriosity(q) {
      const input = document.getElementById(`answer-${q.question_id}`);
      const answer = input.value;
      const data = await api("/api/curiosity/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset: currentDataset,
          concept: q.concept,
          question: q.question,
          answer
        })
      });
      const discovered = [...new Set((data.discovered_concepts || []).map(item => item.concept))].join(", ");
      const ruleCount = (data.new_rules || []).length;
      const inferenceCount = (data.inferences || []).length;
      const summary = [
        discovered ? `发现新概念: ${discovered}` : "",
        ruleCount ? `形成新规则: ${ruleCount}` : "",
        inferenceCount ? `产生推理: ${inferenceCount}` : ""
      ].filter(Boolean).join("\n");
      document.getElementById("curiosityResult").textContent = (summary ? summary + "\n\n" : "") + JSON.stringify(data, null, 2);
      await loadConcept(data.concept);
      await loadCuriosity();
      await loadRules();
    }

    async function ingestKnowledge() {
      const text = document.getElementById("knowledgeText").value;
      const data = await api("/api/knowledge/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset: currentDataset, text })
      });
      const summary = [
        `吸收 claims: ${data.claim_count}`,
        `生成 evidence: ${data.evidence_count}`,
        `更新概念: ${data.updated_concepts.join(", ")}`
      ].join("\n");
      document.getElementById("knowledgeResult").textContent = summary + "\n\n" + JSON.stringify(data, null, 2);
      await loadConcepts();
      await loadCuriosity();
      await loadRules();
    }

    async function loadRules() {
      const data = await api(`/api/rules?dataset=${encodeURIComponent(currentDataset)}`);
      const node = document.getElementById("rules");
      node.innerHTML = "";
      if (!data.rules.length) { node.innerHTML = '<span class="muted">暂无规则。</span>'; return; }
      data.rules.forEach(rule => {
        const div = document.createElement("div");
        div.className = "question-card";
        div.textContent = `${rule.subject_concept}.${rule.predicate} -> ${rule.object_value}; exceptions=${rule.exceptions.join(", ")}; confidence=${rule.confidence}`;
        node.appendChild(div);
      });
    }

    async function runInquiryLoop() {
      const maxSteps = Number(document.getElementById("inquirySteps").value || "10");
      const data = await api("/api/inquiry/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset: currentDataset, max_steps: maxSteps })
      });
      const summary = [
        `完成步数: ${data.completed_steps}`,
        `provider: ${data.provider}`
      ].join("\n");
      document.getElementById("inquiryResult").textContent = summary + "\n\n" + JSON.stringify(data, null, 2);
      await loadConcepts();
      await loadCuriosity();
      await loadRules();
    }

    async function loadAll() {
      currentConcept = "";
      await loadDatasets();
      await loadConcepts();
      await loadCuriosity();
      await loadRules();
    }
    loadAll().catch(err => document.getElementById("answer").textContent = err.message);
  </script>
</body>
</html>
"""


class AthenaConsoleHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML)
            return
        if parsed.path == "/api/datasets":
            self._send_json({
                "datasets": list_datasets(),
                "default_dataset": default_dataset(),
            })
            return
        if parsed.path == "/api/concepts":
            query = parse_qs(parsed.query)
            dataset = query.get("dataset", [default_dataset()])[0]
            engine = engine_for(dataset)
            concepts = [
                {
                    "name": concept.name,
                    "maturity": concept.maturity,
                    "confidence": concept.confidence,
                    "attributes": len(concept.attributes),
                    "relations": len(concept.relations),
                }
                for concept in sorted(engine.graph.all_concepts(), key=lambda item: item.name)
            ]
            self._send_json({"concepts": concepts})
            return
        if parsed.path == "/api/concept":
            query = parse_qs(parsed.query)
            dataset = query.get("dataset", [default_dataset()])[0]
            name = query.get("name", [""])[0]
            engine = engine_for(dataset)
            concept = engine.graph.get_or_create(resolve_name(name))
            self._send_json({
                "concept": concept_to_dict(concept),
                "description": engine.describe_concept(concept.name),
            })
            return
        if parsed.path == "/api/curiosity":
            query = parse_qs(parsed.query)
            dataset = query.get("dataset", [default_dataset()])[0]
            engine = engine_for(dataset)
            self._send_json({"questions": engine.propose_curiosity_questions(limit=24)})
            return
        if parsed.path == "/api/rules":
            query = parse_qs(parsed.query)
            dataset = query.get("dataset", [default_dataset()])[0]
            engine = engine_for(dataset)
            self._send_json({
                "rules": [rule_to_dict(rule) for rule in engine.rules.values()]
            })
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/ask":
            payload = self._read_json()
            dataset = payload.get("dataset") or default_dataset()
            question = payload.get("question", "")
            answer = answer_question(dataset, question)
            self._send_json(answer)
            return
        if parsed.path == "/api/curiosity/answer":
            payload = self._read_json()
            dataset = payload.get("dataset") or default_dataset()
            engine = engine_for(dataset)
            result = engine.answer_curiosity_question(
                concept_name=payload.get("concept", ""),
                question=payload.get("question", ""),
                answer=payload.get("answer", ""),
            )
            self._send_json(result)
            return
        if parsed.path == "/api/knowledge/ingest":
            payload = self._read_json()
            dataset = payload.get("dataset") or default_dataset()
            engine = engine_for(dataset)
            result = engine.ingest_knowledge_text(
                text=payload.get("text", ""),
            )
            self._send_json(result)
            return
        if parsed.path == "/api/inquiry/run":
            payload = self._read_json()
            dataset = payload.get("dataset") or default_dataset()
            engine = engine_for(dataset)
            result = engine.run_inquiry_loop(
                max_steps=int(payload.get("max_steps", 10)),
            )
            self._send_json(result)
            return
        self.send_error(404, "Not found")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_html(self, html: str) -> None:
        encoded = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def list_datasets() -> list[str]:
    if not DATA_ROOT.exists():
        return []
    return sorted(
        path.name
        for path in DATA_ROOT.iterdir()
        if path.is_dir() and any(path.glob("*/*.json"))
    )


def default_dataset() -> str:
    datasets = list_datasets()
    if DEFAULT_DATASET in datasets:
        return DEFAULT_DATASET
    return datasets[0] if datasets else DEFAULT_DATASET


def engine_for(dataset: str) -> CognitiveEngine:
    return CognitiveEngine(DATA_ROOT / dataset)


def resolve_name(value: str) -> str:
    aliases = {
        "苹果": "Apple",
        "桃子": "Peach",
        "梨": "Pear",
        "香蕉": "Banana",
        "番茄": "Tomato",
        "塑料苹果": "PlasticApple",
        "水果": "Fruit",
    }
    stripped = value.strip()
    return aliases.get(stripped, stripped)


def extract_concept_name(question: str, concepts: list[str]) -> str | None:
    normalized_question = question.lower()
    for concept in sorted(concepts, key=len, reverse=True):
        if concept.lower() in normalized_question:
            return concept
    for chinese, english in {
        "苹果": "Apple",
        "桃子": "Peach",
        "梨": "Pear",
        "香蕉": "Banana",
        "番茄": "Tomato",
        "塑料苹果": "PlasticApple",
        "水果": "Fruit",
    }.items():
        if chinese in question and english in concepts:
            return english
    match = re.search(r"描述一下\s*([A-Za-z]+)", question)
    if match:
        return match.group(1)
    return None


def answer_question(dataset: str, question: str) -> dict:
    engine = engine_for(dataset)
    concept_names = [concept.name for concept in engine.graph.all_concepts()]
    concept_name = extract_concept_name(question, concept_names)
    if not concept_name:
        return {
            "answer": (
                "我现在还没有 LLM，所以只能回答有限的问题。"
                "你可以问：描述 Apple、Fruit 有什么特点、描述塑料苹果。"
            ),
            "concept": None,
        }
    return {
        "answer": engine.describe_concept(concept_name),
        "concept": concept_name,
    }


def concept_to_dict(concept) -> dict:
    from dataclasses import asdict

    return asdict(concept)


def rule_to_dict(rule) -> dict:
    from dataclasses import asdict

    return asdict(rule)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    host = "127.0.0.1"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer((host, port), AthenaConsoleHandler)
    print(f"Athena Brain Console: http://{host}:{port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
