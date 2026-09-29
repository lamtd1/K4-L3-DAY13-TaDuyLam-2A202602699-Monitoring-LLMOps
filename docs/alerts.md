# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: `latency_slo_burn`
- Severity: Critical
- Duration: 5 phút liên tục
- Kênh thông báo: Slack `#day13-llmops-alerts`
- SLI/SLO liên quan: `primary_slo.fast_successful_requests` trong `config/slo.yaml` (good event: `latency_ms <= 3000`, target 99.5%, error budget 0.5%/28 ngày).
- Điều kiện và thời gian duy trì: `p95(latency_ms)` trên event `response_sent` (panel `latency` trong `config/dashboard.yaml`) vượt ngưỡng 3000 ms, duy trì liên tục 5 phút.
- Ảnh hưởng tới người dùng: Người dùng chờ câu trả lời lâu bất thường; nếu kéo dài sẽ đốt error budget của SLO chính và có thể gây timeout ở client.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel `latency` (P50/P95/P99, TTFT) để xác nhận mức tăng và thời điểm bắt đầu.
  2. Lọc `data/logs.jsonl` theo khoảng thời gian đó, lấy `correlation_id` của các request có `latency_ms` cao nhất.
  3. Mở trace Langfuse cùng `correlation_id` để xem waterfall — so sánh thời lượng span `retrieve-context` và `llm-generate` để biết bước nào chậm.
- Mitigation tạm thời: Nếu retrieval là nguyên nhân (RAG chậm/timeout), tắt tính năng retrieval nâng cao hoặc fallback về câu trả lời không cần context; nếu LLM chậm, giảm tải bằng cách giới hạn concurrency ở load test/production.
- Owner: TaDuyLam (2A202602699)

## Alert 2

- Tên: `elevated_error_rate`
- Severity: Critical
- Duration: 5 phút liên tục
- Kênh thông báo: Slack `#day13-llmops-alerts`
- SLI/SLO liên quan: guardrail `error_rate_pct_max: 2` trong `config/slo.yaml`; panel `errors` trong `config/dashboard.yaml`.
- Điều kiện và thời gian duy trì: `count(request_failed) / count(request_received) * 100` vượt 2%, duy trì liên tục 5 phút.
- Ảnh hưởng tới người dùng: Một phần yêu cầu trả về lỗi (HTTP 500) thay vì câu trả lời; trải nghiệm người dùng gián đoạn.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel `errors` để xem breakdown theo `error_type` trong cùng khoảng thời gian.
  2. Lọc log `event == "request_failed"`, đọc `error_type` và `tool_name`/`tool_success` để biết lỗi đến từ retrieval hay tầng khác.
  3. Lấy `correlation_id` của một request lỗi, mở trace tương ứng để xác định span nào ném exception.
- Mitigation tạm thời: Nếu lỗi tập trung ở `tool_name=retrieval`, bật fallback trả lời không cần retrieval; nếu lỗi lan rộng ở nhiều feature, tạm thời giảm concurrency/tắt endpoint để tránh cascading failure.
- Owner: TaDuyLam (2A202602699)

## Alert 3

- Tên: `retrieval_success_degraded`
- Severity: Warning
- Duration: 10 phút liên tục
- Kênh thông báo: Slack `#day13-llmops-alerts`
- SLI/SLO liên quan: guardrail `retrieval_success_rate_pct_min: 90` trong `config/slo.yaml`; panel `errors` (retrieval success) trong `config/dashboard.yaml`.
- Điều kiện và thời gian duy trì: `count(tool_success == true) / count(tool_success != null) * 100` dưới 90%, duy trì liên tục 10 phút.
- Ảnh hưởng tới người dùng: Câu trả lời thiếu context liên quan (retrieval thất bại), chất lượng câu trả lời giảm dù request vẫn trả về 200.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel `errors` phần retrieval success rate và panel `quality` để xem quality_score có giảm tương ứng không.
  2. Lọc log có `tool_name == "retrieval"` và `tool_success == false`, lấy `correlation_id` mẫu.
  3. Mở trace Langfuse của span `retrieve-context` tương ứng để xem lỗi/timeout cụ thể từ vector store giả lập.
- Mitigation tạm thời: Kiểm tra `scripts/inject_incident.py` xem có scenario `tool_fail`/`rag_slow` đang bật không và tắt nó; nếu là sự cố thật, tạm thời dùng corpus fallback tĩnh thay vì gọi retrieval.
- Owner: TaDuyLam (2A202602699)
