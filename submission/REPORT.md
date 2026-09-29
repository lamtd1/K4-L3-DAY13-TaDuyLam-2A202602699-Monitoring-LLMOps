# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Tạ Duy Lam
- **MSSV:** 2A202602699
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/lamtd1/K4-L3-DAY13-TaDuyLam-2A202602699-Monitoring-LLMOps.git
- **Commit SHA cuối:** 3f7e610808638572003c4c1e9d1fcb69a90a4f6b
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602699` 

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.txt` |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.txt` |
| PII redaction | `evidence/05-pii-redaction.txt` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` (cần bổ sung: bấm "Raw" trên span `lab-agent-run` để lộ `correlation_id`/prompt version/label) |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-promote.png` (trước: production→v4) và `evidence/10-prompt-rollback.png` (sau: production→v3) |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.txt` |
| Incident log | `evidence/13-incident-log.txt` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | Estimated Score: 30/100 — 20/21 records thiếu required fields, 20/21 thiếu enrichment (context), 0 correlation ID unique | **100/100** (`evidence/02-log-validator.txt`) — 98 records, 0 missing required, 0 missing enrichment, 43 unique correlation ID, 0 PII leak | Sau khi implement correlation ID middleware, context enrichment (`user_id_hash`, `session_id`, `feature`, `model`) và PII scrubbing processor, validator đạt tối đa. Baseline log gốc (21 dòng) đã được lưu riêng tại `data/logs0.jsonl` trước khi đo lại theo đúng hướng dẫn CP1. |
| `validate_dashboard.py` | HỢP LỆ: 6/6 panel có trong dashboard contract | **HỢP LỆ: 6/6 panel** (`evidence/03-dashboard-validator.txt`) | Contract đạt từ baseline; phần còn lại của CP2 là dựng dashboard runtime thật (Streamlit, `scripts/dashboard_app.py`) đọc đúng `data/logs.jsonl` theo contract này. |
| `pytest` | 100% pass | **22/22 pass** (`evidence/01-pytest.txt`) | Bổ sung child observations (retrieval + generation span) trong `app/agent.py` và cập nhật `tests/test_agent_prompt_trace.py` để assert đúng cấu trúc span cha-con, model, usage, cost. |
| Số traces hợp lệ | 0 (chưa cấu hình Langfuse tracing) | ≥30 traces trong project Langfuse cá nhân (2 đợt load test, prompt versioning baseline/candidate/promote/rollback, 1 PII test) | Xem `evidence/06-trace-list.png`. |
| Số PII leak | 0 (validator: `[PASSED] PII scrubbing`) | 0 — `evidence/05-pii-redaction.txt` cho thấy email/SĐT/CCCD/thẻ tín dụng giả đều bị scrub trước khi ghi log | `scrub_text()` chạy trước khi structlog serialize, nên payload trên đĩa không bao giờ chứa PII thô. |
| Latency P50/P95/P99, TTFT P95 | Chưa đo | Baseline (trước incident, traffic=20): P50=398ms, P95=2305ms, P99=2305ms, TTFT P95=55ms. Trong challenge (5 request, `rag_slow`): latency mỗi request ≈2660-2665ms | Số baseline lấy từ `/metrics` (in-memory, cumulative theo phiên chạy server) — xem chi tiết mục 7. |
| Retrieval success rate | Chưa đo | 100% (`tool_success=true` trên toàn bộ `response_sent` records kể cả trong challenge — `rag_slow` làm retrieval **chậm**, không làm nó **fail**) | Phân biệt rõ: guardrail `retrieval_success_rate_pct_min: 90` đo tỷ lệ thành công/thất bại, không đo latency của retrieval. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` ([app/middleware.py](../app/middleware.py)) chạy trên mỗi request: gọi `clear_contextvars()` để tránh rò rỉ context giữa các request, sau đó lấy header `x-request-id` nếu client gửi sẵn, hoặc sinh mới theo format `req-<8-hex>` (`f"req-{uuid.uuid4().hex[:8]}"`). ID này được `bind_contextvars(correlation_id=...)` để structlog tự động gắn vào mọi log line trong request đó, lưu vào `request.state.correlation_id`, và trả lại cho client qua header `x-request-id` cùng `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** Ngay khi nhận request, `app/main.py` bind thêm `user_id_hash` (SHA-256 rút gọn, không lưu `user_id` thô), `session_id`, `feature`, `model`, `env` vào context — nên tất cả log line sau đó (`request_received`, `response_sent`, `request_failed`) đều tự động có đủ các field này cộng với `correlation_id`, `ts`, `level`, `event`. Ví dụ thật: `evidence/04-structured-log.txt`.
- **Cách bảo đảm PII được scrub trước khi ghi:** `app/pii.py` có `scrub_text()` áp các regex cho email, SĐT VN, CCCD, thẻ tín dụng, passport, API key, bearer token, thay bằng nhãn `[REDACTED_<TYPE>]`. Hàm này được gọi tại nơi log được tạo ra (`summarize_text()` trong `main.py`/`agent.py`) **trước khi** structlog serialize thành JSON và ghi xuống `data/logs.jsonl` — nghĩa là input/output thô của người dùng không bao giờ chạm tới đĩa, chỉ có bản đã scrub.
- **Cách kiểm chứng kết quả:** Gửi 1 request test chứa PII giả (email, SĐT, CCCD, số thẻ) qua `/chat`, sau đó grep đúng `correlation_id` trong `data/logs.jsonl` để xác nhận cả `request_received` lẫn `response_sent` đều không còn PII thô — xem `evidence/05-pii-redaction.txt`. Đồng thời `scripts/validate_logs.py` dùng bộ regex **độc lập** với implementation để rà toàn bộ file, kết quả 0 PII leak (`evidence/02-log-validator.txt`).

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Toàn bộ traces được tạo bằng cách tự chạy `python scripts/load_test.py` (2 lần, tổng 15 request qua `data/sample_queries.jsonl`), `python scripts/manage_prompt_versions.py run/promote/rollback` (5 lần) và 1 request test PII — tất cả gửi thẳng tới project Langfuse cá nhân `day13-k4-l3a-<MSSV>` bằng `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` trong `.env` của chính tôi (không dùng key/project của ai khác). Evidence: `evidence/06-trace-list.png`, thấy tên project + ≥10 trace.
- **Cấu trúc root/retrieval/generation observations:** `app/agent.py` (`LabAgent.run`) là root observation `lab-agent-run` (`as_type="agent"`, decorator `@observe`). Bên trong, dùng `langfuse_client.start_as_current_observation()` (Langfuse Python SDK v4) tạo 2 child observation: `retrieve-context` (`as_type="retriever"`, bọc quanh `mock_rag.retrieve()`) và `llm-generate` (`as_type="generation"`, bọc quanh `FakeLLM.generate()`, có `model`, `usage_details` (input/output tokens), `cost_details`). Cả hai chỉ nhận input/output là bản đã `summarize_text()` (PII-scrubbed preview), không bao giờ log input/output thô. Evidence waterfall: `evidence/07-trace-waterfall.png`.
- **Cách nối trace với log:** Cả log JSON và trace Langfuse đều mang cùng `correlation_id` (log qua `bind_contextvars`, trace qua `propagate_attributes(metadata={"correlation_id": ...})` gắn trên span gốc). Muốn tìm trace của 1 log line cụ thể chỉ cần lấy `correlation_id` từ log rồi search/filter đúng giá trị đó trong Metadata của trace. Evidence: `evidence/08-trace-metadata.png`.
- **Prompt name:** `day13-chat` (biến môi trường `LANGFUSE_PROMPT_NAME`).
- **Version/label baseline:** Chạy `python scripts/manage_prompt_versions.py setup` 2 lần (lần đầu lúc 16:33, lần 2 lúc 17:01 — không cố ý, nên prompt hiện có 4 version thay vì 2), mỗi lần tạo 1 cặp version mới với cùng nội dung. Version **baseline/production hiện hành là v3** (`Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}`, gắn label `baseline` + `production`); v1 có nội dung giống hệt nhưng không còn giữ label (bị v3 ghi đè khi label là duy nhất theo tên).
- **Version/label candidate:** **v4** hiện hành, cùng 3 biến bắt buộc, thêm câu "Answer in at most 3 concise sentences." để giới hạn độ dài, gắn label `candidate` + `latest`; v2 có nội dung giống hệt nhưng không còn label. Evidence danh sách đầy đủ 4 version: `evidence/09-prompt-versions.png`.
- **Trace ID của mỗi version (đợt chạy đầu, trên v1/v2 lúc còn giữ label):** `label=baseline` → `correlation_id=req-e63fe0c5`; `label=candidate` → `correlation_id=req-19018789`; sau khi promote `production→v2` → `correlation_id=req-c96027ad`; sau khi rollback `production→v1` → `correlation_id=req-dcd82b3e`. Các trace này vẫn tra được trong Langfuse bằng `correlation_id`, `prompt_version` trong metadata sẽ ghi đúng `2`/`1` tại thời điểm request chạy (không đổi ngược dù label sau này bị v3/v4 lấy lại).
- **Cách promote và rollback `production` (đợt cuối, dùng làm evidence chính thức 09/10):** Dùng `client.update_prompt(name="day13-chat", version=N, new_labels=["production"])` qua lệnh `python scripts/manage_prompt_versions.py promote --version 4` rồi `rollback --version 3`. Langfuse tự động gỡ label `production` khỏi version cũ khi gán cho version mới (label là duy nhất theo tên). Trạng thái cuối cùng sau khi hoàn tất demo: `production` trỏ về **v3** (đã rollback). Evidence trước/sau: `evidence/10-prompt-promote.png` (production→v4), `evidence/10-prompt-rollback.png` (production→v3).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dựng bằng Streamlit tại [scripts/dashboard_app.py](../scripts/dashboard_app.py), đọc trực tiếp `data/logs.jsonl` theo đúng contract [config/dashboard.yaml](../config/dashboard.yaml) (đã pass `validate_dashboard.py`, `evidence/03-dashboard-validator.txt`): (1) Latency P50/P95/P99 + TTFT P95, (2) Traffic (request/phút), (3) Errors (error rate, breakdown theo `error_type`, retrieval success rate), (4) Cost (tổng theo phút + toàn cửa sổ), (5) Tokens in/out, (6) Quality proxy (`quality_score` trung bình). Mỗi panel hiện tên, đơn vị, time range 60 phút (mặc định tính từ log mới nhất) và 1 đường threshold/SLO đỏ lấy đúng giá trị từ `config/dashboard.yaml`. Chạy bằng `streamlit run scripts/dashboard_app.py`. Evidence: `evidence/11-dashboard-overview.png`.
- **SLO và lý do chọn:** [config/slo.yaml](../config/slo.yaml) định nghĩa 1 primary SLO `fast_successful_requests`: good event = `response_sent` có `latency_ms <= 3000`, total event = `request_received`, target 99.5% trong cửa sổ 28 ngày. Giữ nguyên ngưỡng 3000ms vì nó khớp với threshold của panel `latency` (P95 ≤ 3000ms) — nghĩa là SLO chính là "P95 latency panel không báo đỏ liên tục". Điểm cần lưu ý (tự đánh giá): ngưỡng 3000ms **lỏng hơn** ngưỡng riêng của challenge (`latency_threshold_ms: 2000`) — 5 request bị `rag_slow` (≈2660ms) vẫn nằm dưới 3000ms nên không tính là "bad event" theo SLO này dù rõ ràng là bất thường so với baseline (~150-500ms). Nếu muốn SLO nhạy hơn với đúng loại incident này, nên hạ `target` xuống ngưỡng 2000ms hoặc thêm 1 SLO phụ theo P95 của riêng feature `monitoring`.
- **Cách tính error budget:** Công thức: `error_budget_events = (1 - target/100) × total_events` trong cửa sổ. Với target 99.5% → error budget = 0.5% tổng số `request_received` trong 28 ngày được phép có `latency_ms > 3000` mà vẫn đạt SLO. Ví dụ với dữ liệu thật đã thu thập trong lab: tổng `request_received` = 41, số request có `latency_ms > 3000` = 0 (kể cả 5 request trong challenge, vì 2660ms < 3000ms) → error budget đã dùng = 0/41 = 0%, còn nguyên 0.5% budget. Nếu ngoại suy sang production với ví dụ 10.000 request/28 ngày, error budget = 0.5% × 10.000 = **50 request** được phép vượt 3000ms trong cả cửa sổ trước khi vi phạm SLO.
- **Ba alert và runbook tương ứng:** Định nghĩa trong [config/alert_rules.yaml](../config/alert_rules.yaml), runbook chi tiết trong [docs/alerts.md](../docs/alerts.md):
  1. `latency_slo_burn` — P95 latency > 3000ms trong 5 phút liên tục, severity critical, dựa trực tiếp trên primary SLO.
  2. `elevated_error_rate` — error rate > 2% trong 5 phút, severity critical, dựa trên guardrail `error_rate_pct_max`.
  3. `retrieval_success_degraded` — retrieval success rate < 90% trong 10 phút, severity warning, dựa trên guardrail `retrieval_success_rate_pct_min`.
  Cả 3 đều symptom-based (dựa trên triệu chứng người dùng thấy được, không dựa tên hàm/class nội bộ), có Slack channel `#day13-llmops-alerts`, owner và runbook link `docs/alerts.md#alert-N`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (`config/challenge.json`, incident `rag_slow`, không commit file này).
- **Khoảng thời gian điều tra:** `2026-09-29T09:42:53Z` → `09:43:07Z` (UTC), ngay sau khi chạy `python scripts/inject_incident.py` (bật `rag_slow`) và `python scripts/load_test.py --challenge --concurrency 5`.
- **Triệu chứng từ metrics:** `/metrics` baseline (trước incident, traffic=20): `latency_p95 = 2305ms`. Sau 5 request challenge (traffic=25): `latency_p95 = 2664ms`, và riêng 5 request feature `monitoring` có `latency_ms` cá nhân ≈2659-2665ms — cao hơn hẳn baseline non-incident (~150-500ms) và vượt ngưỡng riêng của challenge `latency_threshold_ms: 2000`. Evidence: `evidence/12-incident-metric.txt`.
- **Log line và correlation ID liên quan:** Lọc `data/logs.jsonl` theo feature `monitoring` trong khung giờ trên, lấy 1 request đại diện: `correlation_id = req-478abc54`, `event=response_sent`, `latency_ms=2665`, `tool_name=retrieval`, `tool_success=true` (retrieval **chậm**, không lỗi). Evidence: `evidence/13-incident-log.txt`.
- **Trace ID và span gây ảnh hưởng:** Trace `3c39d90594c5fa48cb5d953121d423ec` (cùng `correlation_id=req-478abc54`, verify khớp timestamp `request_received` = start time của span gốc). Waterfall: `lab-agent-run` (2660-2665ms tổng) gồm `retrieve-context` = **2506ms (94%)** và `llm-generate` = **159ms**. Span `retrieve-context` là span gây ảnh hưởng. Evidence: `evidence/14-incident-trace.png`.
- **Root cause:** Incident `rag_slow` chèn `time.sleep(2.5)` vào `mock_rag.retrieve()` ([app/mock_rag.py](../app/mock_rag.py)) khi `STATE["rag_slow"]=True`. Con số 2506ms đo được trên span khớp với 2.5s sleep này (chênh lệch nhỏ do overhead xử lý khác). Vì FastAPI chạy endpoint đồng bộ trong 1 event loop (single worker), độ trễ này còn khuếch đại thêm khi có nhiều request đồng thời (queueing) — quan sát được qua độ trễ client-side lên tới ~13s khi `--concurrency 5`, dù latency nội bộ mỗi request chỉ ~2.6s.
- **Fix action:** Thêm timeout/circuit breaker quanh lời gọi retrieval, fallback về corpus tĩnh/cached khi vector store phản hồi chậm, tránh block toàn bộ request. Trong lab, xử lý ngay bằng cách tắt incident: `python scripts/inject_incident.py --disable` sau khi đã thu đủ evidence.
- **Preventive measure:** Tách latency budget theo từng span (ví dụ: retrieval ≤500ms trong tổng ngân sách 3000ms) và thêm alert riêng theo duration của span `retrieve-context` thay vì chỉ theo latency tổng — đây chính là lý do alert `retrieval_success_degraded` (mục 6) được thiết kế theo tỷ lệ thành công/thất bại của tool, cần bổ sung thêm 1 alert theo **latency** của retrieval để bắt được đúng loại incident này sớm hơn.

## 8. Giải thích và tự đánh giá

> Mục này cần bạn tự đọc lại và điều chỉnh theo đúng trải nghiệm của mình trước khi nộp — nội dung dưới đây phản ánh đúng các quyết định/blocker thật đã xảy ra trong quá trình làm, nhưng phần Q&A demo sẽ hỏi trực tiếp bạn nên cần hiểu rõ, không chỉ đọc thuộc.

- **Một quyết định kỹ thuật quan trọng và lý do:** Bọc `retrieve()` và `FakeLLM.generate()` bằng `start_as_current_observation()` thay vì chỉ ghi metadata lên span gốc, vì mục tiêu CP2 là phải thấy **waterfall** (thời lượng từng bước) chứ không chỉ biết prompt nào được dùng. Chỉ cần tách 2 span con là đã đủ trả lời câu hỏi "bước nào chậm" mà không cần thêm framework tracing riêng.
- **Một lỗi/blocker đã gặp:** Khi gọi `client.api.trace.list()` để lấy trace theo `session_id`, Langfuse trả lỗi `410 LEGACY_API_UNAVAILABLE_FOR_NEW_ORGANIZATION` vì project mới (tạo sau 16/09/2026) không còn hỗ trợ API `traces` cũ; phải chuyển sang `client.api.observations.get_many(session_id=...)` (API v2) để lấy đúng dữ liệu observation.
- **Cách tìm nguyên nhân và xử lý:** Đọc thẳng message lỗi trả về (Langfuse trả kèm `replacementEndpoint` và link migration trong body lỗi), đổi sang endpoint được đề xuất, rồi verify lại bằng cách so khớp `start_time` của observation với `ts` của log line cùng `correlation_id` — đảm bảo lấy đúng trace, không nhầm giữa nhiều lần chạy có cùng `session_id` (ví dụ challenge chạy 2 lần do thao tác lặp, phải đối chiếu timestamp để chọn đúng lần chạy chính thức).
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics cho biết **có/không có vấn đề và khoảng thời gian**, nhưng là số tổng hợp trên nhiều request nên không chỉ ra request cụ thể. Logs (qua `correlation_id`) thu hẹp xuống **một request cụ thể** kèm context (feature, model, tool), nhưng chỉ có latency tổng, không thấy bên trong request đó tốn thời gian ở đâu. Trace mở "hộp đen" của chính request đó, cho thấy **span nào** chiếm phần lớn thời gian. Ba nguồn phải cùng khớp một `correlation_id`/khung giờ thì kết luận root cause mới hợp lệ — đúng như chuỗi đã dùng ở mục 7 (`req-478abc54` khớp cả log lẫn trace `3c39d90594c5fa48cb5d953121d423ec`).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version/label tách biệt "đang chạy prompt nào" khỏi code, cho phép đổi hành vi model (`baseline` → `candidate` → `production`) mà không deploy lại, và **rollback tức thời** nếu candidate gây lỗi — đây là cơ chế giảm rủi ro quan trọng nhất khi vận hành LLM vì output của LLM khó test đầy đủ trước khi chạy thật. Token/cost theo dõi trên từng generation giúp phát hiện cost spike sớm (guardrail `daily_cost_usd_max`). SLO + error budget biến "latency cao" từ cảm tính thành 1 con số có ngưỡng rõ ràng, để quyết định khi nào cần alert/rollback thay vì phản ứng theo cảm giác.
- **Điều quan trọng nhất đã học:** Metric tổng hợp (percentile trên toàn bộ lịch sử in-memory) có thể **che mất** một incident thật nếu cửa sổ đo quá rộng hoặc lẫn dữ liệu cũ — phải luôn đối chiếu với log/trace của đúng khung giờ nghi ngờ thay vì chỉ nhìn con số dashboard tổng.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Ảnh evidence Langfuse (06-10, 14) và dashboard runtime (11) cần tự chụp trực tiếp từ trình duyệt/tài khoản Langfuse cá nhân vì không thể chụp thay; danh sách chính xác cần chụp đã liệt kê ở mục 2.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối. _(chưa commit)_
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối (đã dẫn trong mục 2).
- [x] Incident evidence nối đúng metric → log → trace (mục 7: `req-478abc54` ↔ trace `3c39d90594c5fa48cb5d953121d423ec`).
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret. _(tự rà lại từng ảnh 06-10,14 trước khi nộp — đặc biệt không chụp trang API Keys)_
- [ ] Repository chạy lại được theo README. _(tự chạy lại `pip install -r requirements.txt` trên máy sạch để xác nhận)_
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác. _(evidence .txt đã kiểm tra không chứa PII/secret; tự rà lại ảnh .png)_
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs. _(cần: tạo repo GitHub cá nhân, push, điền vào mục 1, nộp trước 23:59:59 giờ VN)_
