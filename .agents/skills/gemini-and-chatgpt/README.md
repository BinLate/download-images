# Gemini + ChatGPT Automatic Code Review

## Mục tiêu

Bộ này biến Antigravity thành **thợ code + điều phối**, còn ChatGPT Web thành **người review độc lập**.

Sau khi cài một lần, bạn chỉ cần giao task code bình thường cho Antigravity. Không cần gõ `Use gemini-and-chatgpt skill` mỗi lần.

## Reviewer transport hiện tại: một Browser Subagent task end-to-end

Sau khi PR đã OPEN và candidate SHA đã verify:

1. `review_round.py prepare --root .` tạo immutable `reviewer-prompt.txt` và trả về `prompt_path`, `response_path`.
2. Main Agent đọc **toàn bộ** `reviewer-prompt.txt` bằng `view_file`, rồi truyền nguyên văn nội dung đó vào **một** `browser_subagent` task.
3. Browser Subagent mở/reuse ChatGPT, tạo fresh conversation, nhập toàn bộ prompt thành một draft, verify đủ BEGIN + END marker, click Send đúng một lần, chờ ChatGPT trả lời xong và trả về toàn bộ response. Nếu prompt đã nằm đầy đủ trong composer thì chỉ verify marker rồi click Send, không gõ lại.
4. Main Agent ghi nguyên văn response vào `reviewer-response.txt`, rồi chạy `review_round.py finalize --root .` để kiểm tra exact SHA/session/manifest, parse verdict và cập nhật lifecycle.

Không dùng clipboard. Không nhấn bare Enter khi đang soạn prompt. Không còn phase `transport`, không còn PowerShell/CDP browser handoff và không mở reviewer Chrome/profile riêng.


Luồng mặc định:

```text
Bạn giao task
   ↓
Antigravity phân tích + code
   ↓
Test / lint / build
   ↓
Tạo hoặc cập nhật GitHub Pull Request
   ↓
Mở ChatGPT Web để review đúng HEAD SHA
   ↓
REQUEST_CHANGES ? ── Có ──> Antigravity sửa + test lại + push + review lại
   │
   Không
   ↓
APPROVED_TO_MERGE
   ↓
Dừng ở release gate (không tự merge mặc định)
```

---

# Cách cài đơn giản nhất

Giả sử project của bạn là:

```text
D:\Code\my-project\
```

Chỉ cần copy **nguyên thư mục** `gemini-and-chatgpt` vào root project:

```text
D:\Code\my-project\
├── gemini-and-chatgpt\
│   ├── INSTALL-ANTIGRAVITY.bat
│   ├── SKILL.md
│   ├── README.md
│   ├── scripts\
│   ├── references\
│   └── agents\
├── src\
└── ...
```

Sau đó double-click:

```text
gemini-and-chatgpt\INSTALL-ANTIGRAVITY.bat
```

Installer sẽ tự copy skill vào đúng vị trí Antigravity cần:

```text
<project>\.agents\skills\gemini-and-chatgpt\
```

Bạn không cần tự tạo `.agents\skills\...` nữa.

---

# Sau khi cài, dùng thế nào?

Mở **root project** bằng Antigravity và giao task như bình thường.

Ví dụ:

```text
Sửa lỗi form đăng ký không báo lỗi khi email sai định dạng.
```

Hoặc:

```text
Thêm chức năng tìm kiếm sản phẩm theo tên và danh mục.
```

Không cần thêm câu:

```text
Use the gemini-and-chatgpt skill
```

Skill được thiết kế để Antigravity tự nhận biết workflow coding có PR và tự áp dụng review loop.

Installer còn thêm rule bắt buộc vào `AGENTS.md` của project. Đây là lớp đảm bảo tự động mạnh hơn việc chỉ trông chờ model tự chọn Skill. Sau khi cài hoặc cập nhật, hãy reload/reopen workspace Antigravity một lần.

---

# GitHub cần chuẩn bị gì?

Workflow cần GitHub để tạo Pull Request và dùng PR làm nguồn dữ liệu chung giữa Gemini và ChatGPT.

Máy cần có:

```text
git
gh (GitHub CLI)
```

Installer bây giờ cấu hình GitHub theo **2 tầng**:

1. **Kết nối tài khoản GitHub** bằng `gh auth status` / `gh auth login`.
2. **Kết nối project hiện tại với một GitHub repository** bằng remote `origin`.

Nếu project chưa phải Git repo, installer sẽ hỏi có muốn `git init` tự động hay không. Nếu chưa đăng nhập GitHub, installer cho 3 lựa chọn:

1. **Browser login — khuyến nghị**
2. **Personal Access Token (PAT)**
3. Bỏ qua và cấu hình sau

Sau khi đăng nhập xong, nếu project chưa có `origin`, installer tiếp tục hỏi:

1. **Tạo GitHub repository mới** từ project hiện tại và tự gắn `origin`
2. **Kết nối repository có sẵn** bằng URL GitHub
3. Bỏ qua

Vì vậy lần cài đầu tiên bạn không cần tự chạy `git remote add origin ...` hay `gh repo create` bằng tay.

## Cách khuyến nghị: Browser login

Installer gọi:

```text
gh auth login --web
```

GitHub mở trình duyệt để bạn xác nhận. Không cần copy token vào file nào.

## Nếu muốn dùng Personal Access Token

Bạn có thể dùng PAT. Installer sẽ mở một prompt PowerShell dạng secure input, không ghi token vào `README.md`, `SKILL.md` hoặc file cấu hình của project.

Nếu dùng **Classic PAT** cho private repository, quyền `repo` thường là quyền chính cần thiết cho thao tác repository/PR. Nếu workflow của project phải sửa file GitHub Actions, có thể cần thêm quyền phù hợp cho workflow.

Không nên lưu PAT trực tiếp trong `.bat`, `.env`, prompt AI, commit Git hoặc README.

---

# Thứ tự bắt buộc: GitHub trước, ChatGPT sau

Workflow mới **không được mở ChatGPT review ngay sau khi code xong**. Thứ tự bắt buộc là:

```text
Code xong
  ↓
Test / lint / build
  ↓
Commit branch
  ↓
Push branch lên GitHub
  ↓
Tạo / cập nhật Pull Request
  ↓
Lấy exact HEAD SHA của PR
  ↓
MỚI mở ChatGPT Web để review
```

Nếu chưa đăng nhập GitHub hoặc chưa có `origin`, Antigravity phải dừng và yêu cầu chạy lại `INSTALL-ANTIGRAVITY.bat`; không được bỏ qua GitHub rồi đi thẳng sang ChatGPT.

# ChatGPT cần chuẩn bị gì?

Đăng nhập ChatGPT Web trong browser mà Antigravity có thể điều khiển.

Không cần OpenAI API key.

Khi tới bước review, workflow yêu cầu reviewer kiểm tra:

- PR hiện tại
- exact HEAD SHA
- correctness
- regression
- architecture
- security
- error handling
- test coverage
- production readiness

Mỗi vòng review nên dùng conversation mới để giảm confirmation bias.


### Fast normal path

Để tránh Antigravity chạy hàng loạt Python helper nhỏ, normal flow dùng các boundary gộp:

`orchestrator.py start` → implement → `orchestrator.py verify` → Git push/PR → `review_round.py prepare` → one Antigravity Browser Subagent review → save response → `review_round.py finalize`.

`start` gộp task init + classification; `verify` gộp bind candidate + Central Verification Gate. `prepare` tạo immutable package và exact-SHA session; Browser Subagent làm trọn browser phase (open, nhập prompt, Send, chờ, lấy response); `finalize` kiểm tra lại exact SHA/session/manifest và parse verdict. Không chạy `--help`, `begin-verify`, `delivery`, `pr_context.py`, `transport`, `direct_fill_review_prompt.ps1`, hoặc các standalone reviewer verifier trên happy path. Task một file low-risk vẫn là SIMPLE dù user yêu cầu chạy full GitHub/ChatGPT workflow.

Mỗi lệnh orchestration/review tự append log vào `.ai/gemini-chatgpt-actions.log` và `.ai/gemini-chatgpt-actions.jsonl` mà không spawn thêm command để logging. Khi có lỗi, chỉ cần gửi file `.ai/gemini-chatgpt-actions.log` để chẩn đoán.

Reviewer retry safety: one prepared round gets one Browser Subagent review task. The subagent must not return after merely filling the composer; it must click Send, wait for completion, and return the entire response. If it cannot complete, stop `BLOCKED` instead of looping or switching to clipboard/CDP transports. An already-approved exact HEAD returns `ALREADY_APPROVED` without starting another browser review. Antigravity must not self-patch the Skill or generate scratch transport tests.

---

# gemini-and-chatgpt là gì?

Đây chỉ là **tên nội bộ của Skill**.

Bạn không cần nhớ tên này khi sử dụng hằng ngày.

Installer đặt bộ quy trình vào:

```text
.agents\skills\gemini-and-chatgpt\
```

Antigravity đọc `SKILL.md` trong đó để biết:

- sau khi code phải test
- phải tạo/cập nhật PR
- phải dùng ChatGPT Web review
- phải khóa review theo HEAD SHA
- nếu reviewer yêu cầu thay đổi thì sửa finding hợp lệ
- phải review lại sau mỗi HEAD mới
- dừng sau tối đa 5 vòng
- không tự merge nếu chưa được bật rõ ràng

---

# Điều kiện để chạy full workflow

Project phải có Git repository:

```text
git status
```

Và có GitHub remote:

```text
git remote -v
```

GitHub CLI phải đăng nhập:

```text
gh auth status
```

Nếu project mới hoàn toàn và chưa có GitHub repository, hãy tạo repo GitHub trước hoặc dùng `gh repo create`.

---

# Các thành phần chính

## `SKILL.md`

Control plane chính. Quy định state machine và hành vi của Antigravity.

## `references/builder-contract.md`

Quy tắc cho AI viết code: không sửa lan man, không làm yếu test, không che lỗi, phải kiểm chứng thay đổi.

## `references/review-contract.md`

Protocol ép ChatGPT Web trả verdict rõ ràng:

```text
APPROVED_TO_MERGE
REQUEST_CHANGES
NEEDS_HUMAN_DECISION
```

## `references/workflow.md`

Chi tiết workflow, recovery và state machine.

## `scripts/pr_context.py`

Lấy metadata của PR và exact HEAD SHA để tránh review nhầm commit cũ.

## `scripts/parse_review.py`

Parse kết quả reviewer thành verdict máy có thể xử lý.

## `scripts/workflow_state.py`

Lưu state để workflow có thể tiếp tục sau khi bị dừng/crash.

## `INSTALL-ANTIGRAVITY.bat`

Installer một click dành cho Windows. Tự cài skill vào project và hỗ trợ cấu hình GitHub authentication.


## `scripts/task_classifier.py` và `scripts/plan_store.py` — B3+B4

MVP 1 hiện đã có deterministic task classifier/risk router và durable Planner task graph. Classifier route task thành `SIMPLE`, `STANDARD`, hoặc `COMPLEX`; chỉ `STANDARD/COMPLEX` yêu cầu full `plan.json`.

Planner state được lưu dưới `.ai/tasks/<task-id>/plan.json`; `plan.md` chỉ là projection cho người đọc. Dependency graph phải acyclic, work item chỉ `READY` khi dependencies hoàn tất, và `SKIPPED_WITH_REASON` luôn cần lý do. Dedicated Architect invocation vẫn chưa được kích hoạt ở B3+B4; `architect_required=true` chỉ là routing/risk signal cho các batch orchestration sau.

## `scripts/verification_gate.py` — B5 Central Verification Gate

B5 thêm một Verification Gate deterministic dùng một candidate commit SHA làm identity cho QA. Mỗi check ghi evidence append-only vào `.ai/tasks/<task-id>/verification.jsonl`; task state chỉ nhận `PASS` khi mọi required check đều pass đúng candidate SHA.

Aggregate status gồm `PASS`, `FAIL`, `BLOCKED`, `PARTIAL`. Required check bị `SKIPPED` không thể trở thành PASS; optional check không pass cũng làm kết quả thành `PARTIAL` thay vì bị che đi. Code thay đổi sang candidate SHA mới làm evidence PASS cũ không còn đủ authority cho `PR_PREPARING`.

B5 mới cung cấp gate/evidence semantics; local repair orchestration và việc tự nối gate vào default workflow được thực hiện ở B6.

## `scripts/orchestrator.py` — B6 orchestration integration

B6 thêm entrypoint lifecycle v2 cho task mới. Orchestrator tạo/resume task, route classifier, yêu cầu Planner khi cần, đưa candidate qua Central Verification Gate, kiểm tra PR HEAD phải bằng verified candidate SHA trước review, sở hữu review-round routing và dừng ở `RELEASE_GATE` khi reviewer approve.

`workflow_state.py` hiện là compatibility facade: nếu `.ai/active-task.json` tồn tại, `show/set/next-round` được project/delegate sang authoritative v2 task state; nếu không có active v2 task, hành vi `.ai/review-state.json` cũ vẫn giữ nguyên. Không có hai authoritative state cùng lúc.

B6 giữ GitHub/ChatGPT backend hiện hữu và không auto-merge. B7 harden exact-SHA parser/delivery identity và reviewer prompt.

## `scripts/review_prompt.py` — B7 exact-SHA review package

B7 khóa independent review theo một OPEN PR và exact full 40-character HEAD SHA. `parse_review.py` không còn chấp nhận abbreviated/prefix SHA; `pr_context.py` validate local HEAD, PR HEAD và base SHA ở dạng full SHA, từ chối PR không OPEN, đồng thời invalidates approval cũ khi HEAD thay đổi.

`review_prompt.py` chỉ project dữ liệu reviewer cần: task/scope, acceptance criteria, constraints/assumptions, implementation/changed files, exact PR identity, Verification Gate evidence bind đúng SHA, prior findings/dispositions và reviewer contract. Nó không dump toàn bộ project context hoặc chat history. Mỗi review round vẫn phải dùng fresh ChatGPT Web conversation.

## B8 — activation, installer và MVP exit gate

B8 đóng gói v2 thành một project-local workflow có thể kích hoạt từ coding request bình thường. `SKILL.md` mô tả v2 lifecycle đầy đủ; installer cập nhật một managed block trong project-root `AGENTS.md`, clean-refresh `.agents\skills\gemini-and-chatgpt`, copy cả `schemas/`, và không cài AWF/global workflow thứ hai.

`INSTALL-ANTIGRAVITY.bat` fail-closed nếu bộ source v2 thiếu runtime/reference/schema bắt buộc hoặc nếu BAT bị chạy từ chính installed skill directory. Các Yes/No prompt dùng `(default Y)` khi Enter có nghĩa Yes. Automatic merge vẫn OFF mặc định.

Internal MVP E2E regression kiểm tra đường `task -> classify -> implement -> exact candidate SHA -> Verification Gate PASS -> OPEN PR identity -> exact review HEAD -> reviewer prompt -> verdict -> RELEASE_GATE`, cùng nhánh `REQUEST_CHANGES -> new candidate -> fresh review round`. Runtime hiện tại không có Windows `cmd.exe`/PowerShell hoặc GitHub CLI `gh`, vì vậy BAT/PowerShell execution và GitHub + ChatGPT Web E2E thật phải được xác nhận trên máy Windows/Antigravity; chúng không được giả lập thành PASS.

## `tests/` và `schemas/` — nền tảng MVP 1

MVP 1 hiện đã có regression harness cho review loop v1 và các JSON Schema v2 cho project context, task state, plan, verification evidence và checkpoint. Phần này **chưa thay đổi runtime orchestration hiện tại**; nó tạo safety net và data contracts trước khi triển khai state machine v2.

Chạy regression suite:

```text
python -m unittest discover -s tests -v
```

Schema tests sử dụng `jsonschema` khi chạy development validation.

---

# Safety / Human Gate

Workflow sẽ không cố tự xử lý mọi thứ.

Nó phải dừng hỏi người dùng khi gặp các thay đổi rủi ro cao như:

- destructive database migration
- authentication / authorization quan trọng
- payment
- secrets / credentials
- production infrastructure
- breaking API/schema change
- irreversible data operation
- reviewer và builder bất đồng đáng kể sau nhiều vòng

Automatic merge mặc định **OFF**.

---

# Cách cập nhật tool

Thư mục nguồn chính được duy trì tại:

```text
My Drive\Vibe-Code\awf-plus\gemini-and-chatgpt
```

Khi có phiên bản mới:

1. Đồng bộ/copy bản mới của `gemini-and-chatgpt` vào project nếu cần.
2. Chạy lại `INSTALL-ANTIGRAVITY.bat`.
3. Installer overwrite/cập nhật bản skill trong `.agents\skills\gemini-and-chatgpt`.

---


## MVP 1 implementation status

As of 2026-08-19, B0 through B8 implementation is complete in the canonical source. The deterministic/internal MVP exit gate passes, including activation/installer contract checks and end-to-end lifecycle/review simulations. External release validation is still required on a real Windows/Antigravity machine for BAT/PowerShell execution and on a real GitHub PR + fresh ChatGPT Web session; those environment-dependent checks were not executable in this runtime and are not claimed as PASS.


# Changelog

## 2026-08-19 — Reviewer runtime trace + hard browser timeouts

- Thêm `scripts/review_runtime_log.py` để ghi append-only `review-runtime.jsonl` cho từng phase của Gate E.
- Mặc định Gate E tối đa 15 phút; browser phase 2 phút; reviewer-response wait 5 phút; transport retry tối đa 3 lần.
- Target/clipboard/insert/readback/transport/final-target/send/wait đều phải ghi log; timeout hoặc retry-limit phải dừng `BLOCKED`, không chạy browser vô hạn.
- Log chỉ chứa metadata/evidence cần chẩn đoán; không được ghi cookie, token hoặc browser credential.


### 2026-08-19 — MVP 1 B8 activation, installer, and exit gate
- Updated `SKILL.md` for natural-language auto-activation of the v2 orchestrator, proportional planning, SHA-bound Verification Gate, exact-SHA GitHub delivery, and independent fresh ChatGPT Web review.
- Hardened `INSTALL-ANTIGRAVITY.bat` to validate the complete v2 source, refuse self-install execution, clean-refresh one project-local skill, copy schemas, preserve explicit `(default Y)` prompts, and keep automatic merge OFF.
- Updated `scripts/install_agents_rule.ps1`, `agents/openai.yaml`, and `references/installation.md`; no AWF/global installer layer was added.
- Added B8 activation/installer tests and deterministic MVP internal E2E tests. Current reconstructed working-copy suite: 64/64 PASS; B8-focused tests: 9/9 PASS; Python helpers compile cleanly. The prior full B0-B7 canonical regression checkpoint remains 100 PASS.
- External Windows BAT/PowerShell execution and real GitHub PR -> ChatGPT Web review were not executable in this Linux runtime and remain the final environment validation before a production release claim.


## 2026-08-19 — MVP 1 B6: orchestrator + v1 compatibility

- Thêm `scripts/orchestrator.py` làm lifecycle entrypoint v2.
- `workflow_state.py` trở thành compatibility facade cho active v2 task nhưng vẫn giữ legacy mode.
- Exact verified candidate SHA phải khớp PR HEAD trước review; review round tăng chỉ khi vào fresh review.
- Regression B0-B6: 89 tests pass; auto-merge vẫn OFF.


### 2026-08-19 — MVP 1 B7 exact-SHA review hardening
- Added `scripts/review_prompt.py` with a minimal, allow-listed reviewer projection.
- `parse_review.py` now requires exact 40-character SHA equality; prefix/abbreviated SHA equivalence is removed.
- `pr_context.py` now requires an OPEN PR, full local/PR/base SHAs, and invalidates stale approval when HEAD changes.
- Added review and safety/release policies plus exact-SHA/prompt regression tests.
- Regression result: 100 tests pass; Python helpers compile cleanly.
- B8 activation/installer/internal E2E exit gate is now implemented; external Windows/GitHub/ChatGPT environment validation remains separate.



## 2026-08-19 — MVP 1 B5: Central Verification Gate

- Thêm `scripts/verification_gate.py` với check categories `LINT`, `TYPECHECK`, `FOCUSED_TEST`, `REGRESSION_TEST`, `BUILD`, `INTEGRATION_SMOKE`, `CUSTOM`.
- Evidence được append-only vào `.ai/tasks/<task-id>/verification.jsonl` và bind với full 40-character candidate SHA.
- Required `FAIL` => `FAIL`, required `BLOCKED` => `BLOCKED`, required `SKIPPED` => `PARTIAL`; không có đường tự nâng incomplete verification thành PASS.
- Thêm `references/roles/verifier-contract.md` và `references/policies/verification-policy.md`.
- Regression suite tăng lên 76 tests; B5 chưa tự kích hoạt orchestrator v2 hoặc thay thế review backend v1.


## 2026-08-19 — MVP 1 B3+B4: classifier + planner graph

- Thêm `scripts/task_classifier.py` với taxonomy task kind, `SIMPLE/STANDARD/COMPLEX`, risk level, hard triggers, Planner/Architect/human-precheck flags.
- Thêm `scripts/plan_store.py` với DAG validation, deterministic `plan.md`, dependency-aware READY state, progress sync về authoritative task state và fail-closed skip/cycle handling.
- Thêm `references/roles/planner-contract.md`; refine `plan.schema.json` với scope, constraints, assumptions và risk notes.
- Regression suite tăng từ 41 lên **61 tests**, toàn bộ pass; 5 JSON Schema vẫn pass Draft 2020-12 meta-validation.
- B3+B4 chưa kích hoạt v2 orchestrator, Verification Gate hoặc dedicated Architect execution.

## 2026-08-19 — MVP 1 PR-1 foundation: B0 + B1

- Thêm regression harness trong `tests/` để đóng băng các invariant v1: workflow state, fail-closed reviewer parsing, PR HEAD reconciliation, review-round cap, automatic activation và auto-merge OFF.
- Thêm 5 JSON Schema v2 trong `schemas/`: project context, task state, plan, verification evidence và checkpoint.
- Schema validation yêu cầu full 40-character candidate SHA cho evidence/state v2 và không có field lưu secret value trong project environment context.
- Regression gate hiện có 21 tests; B0+B1 không thay đổi runtime behavior của `workflow_state.py`, `pr_context.py` hoặc `parse_review.py`.
- Sửa đường dẫn source chính trong README thành `My Drive\Vibe-Code\awf-plus\gemini-and-chatgpt`.

## 2026-08-19 — Fix installer closing immediately

- Sửa lỗi cú pháp Batch khi prompt Yes/No có `(default Y)` nằm bên trong khối `if (...)`; lỗi này có thể làm `INSTALL-ANTIGRAVITY.bat` đóng ngay khi mở.
- Các prompt Yes/No giờ dùng cú pháp `set /p "VAR=... (default Y): "` an toàn với CMD; nhấn Enter sẽ chọn `Y`.
- Khôi phục lệnh cài GitHub CLI đúng source: `winget install --id GitHub.cli -e --source winget --accept-package-agreements --accept-source-agreements`.


## 2026-08-18 — Fix GitHub CLI installation source

- Sửa lệnh cài GitHub CLI thành `winget install --id GitHub.cli -e --source winget --accept-package-agreements --accept-source-agreements`.
- Ép `winget` dùng source `winget`, tránh lỗi source `msstore` như `0x8a15005e` làm cài đặt GitHub CLI thất bại.

## 2026-08-18 — Rename skill to gemini-and-chatgpt

- Đổi tên Skill nội bộ từ `ai-pr-review-loop` thành `gemini-and-chatgpt` để trùng hoàn toàn với tên thư mục nguồn.
- Installer giờ cài vào `.agents\skills\gemini-and-chatgpt\`.
- Tự xóa thư mục Skill cũ `.agents\skills\ai-pr-review-loop\` khi chạy lại installer để tránh Antigravity nhìn thấy hai Skill trùng chức năng.
- `AGENTS.md`, đường dẫn script clipboard, tài liệu cài đặt và metadata đều dùng tên `gemini-and-chatgpt`.
- Từ phiên bản này không tạo hoặc duy trì `skill.zip`; làm việc trực tiếp trên các file trong Google Drive.


## 2026-08-18 — GitHub onboarding + clipboard paste

- Installer hỏi rõ GitHub account connection bằng browser login hoặc PAT.
- Nếu project chưa phải Git repo, installer có thể `git init` tự động.
- Sau khi login, installer kiểm tra `origin`; nếu thiếu sẽ hỏi tạo repo GitHub mới hoặc kết nối repo có sẵn bằng URL.
- Workflow cấm mở ChatGPT review trước khi branch đã push và Pull Request đã tồn tại trên GitHub.
- Thêm `scripts/copy_review_prompt.ps1` để copy toàn bộ review prompt vào Windows clipboard và paste một lần bằng `Ctrl+V`, tránh gõ từng ký tự.
- Installer cập nhật lại block trong `AGENTS.md` mỗi lần chạy, không chỉ thêm một lần.



## 2026-08-18 — Automatic activation + fast ChatGPT paste

- Installer giờ tự thêm một block vào `AGENTS.md` ở root project. Antigravity tự đọc file này khi mở workspace, nên không cần nhắc `Use gemini-and-chatgpt skill`.
- Nếu Antigravity đang mở lúc cài, cần reload/reopen workspace một lần để rule mới được nạp.
- Khi gửi prompt review dài sang ChatGPT Web, workflow yêu cầu **verified bulk insert**: clipboard phải được read-back verify trước paste; composer phải được read-back verify trước Send. Direct field fill được phép nếu cũng verify composer. Simulated typing bị tắt mặc định.
- Mục tiêu là tránh mất thời gian vì browser agent mô phỏng gõ hàng nghìn ký tự.

## 2026-08-18 — Simplified installer

- Thêm `INSTALL-ANTIGRAVITY.bat`.
- Cho phép chỉ copy nguyên thư mục `gemini-and-chatgpt` vào root project rồi chạy installer.
- Installer tự tạo `.agents\skills\gemini-and-chatgpt`.
- Không còn yêu cầu người dùng phải gõ `Use the gemini-and-chatgpt skill` trong mỗi prompt.
- Thêm kiểm tra Git và GitHub CLI.
- Thêm GitHub login bằng browser.
- Thêm tùy chọn đăng nhập bằng PAT qua secure PowerShell prompt.
- Không lưu PAT vào project hoặc tài liệu.
- Viết lại hướng dẫn sử dụng theo quy trình một-click.

## 2026-08-18 — Initial version

- Tạo `gemini-and-chatgpt`.
- Builder + GitHub PR + ChatGPT Web reviewer.
- Exact HEAD SHA locking.
- Review loop tối đa 5 vòng.
- State recovery.
- Human safety gate.
- Auto-merge mặc định tắt.

## External MVP validation

MVP 1 implementation and deterministic/internal gates are complete. Production validation additionally requires the Windows/Antigravity/GitHub/ChatGPT Web checklist in `docs/external-mvp-validation-checklist.md`.

The current non-Windows build environment cannot execute `INSTALL-ANTIGRAVITY.bat`, Windows PowerShell, GitHub CLI authentication/PR flow, or the authenticated interactive ChatGPT Web reviewer flow. Therefore the current external verdict is `EXTERNAL_MVP_VALIDATION_BLOCKED`, not PASS.

## 2026-08-19 — Reviewer prompt clipboard race-condition hardening

- `review_prompt.py` emits transport BEGIN/END markers with deterministic `PROMPT_ID` and exact `TARGET_HEAD_SHA` repeated at both boundaries.
- `copy_review_prompt.ps1` performs exact clipboard read-back verification with bounded retry instead of trusting `Set-Clipboard` blindly.
- Added `verify_review_transport.py`: the browser must persist the full composer read-back and pass exact normalized-text + transport-identity verification before Send.
- Clipboard replacement, truncated/partially submitted prompts, wrong prompt IDs, wrong HEADs, or changed middle content all fail closed.
- On mismatch the workflow clears the composer, recopies, reinserts, rereads, and re-verifies; after 3 attempts it stops instead of sending uncertain content.
- Simulated character-by-character typing is disabled by default and is no longer an automatic fallback.


## 2026-08-19 — Reviewer paste-target/focus integrity hardening

- Added `scripts/verify_review_target.py` to fail closed unless the current page is the expected fresh `chatgpt.com` reviewer URL, the document has focus, the composer is visible/enabled, and the exact composer is `document.activeElement`.
- Reviewer transport now verifies target integrity immediately before insertion and again immediately before Send; a changed URL, browser address-bar focus, sidebar/search/body focus, hidden/disabled composer, or unknown target blocks paste/send.
- Direct DOM/field fill is preferred. `Ctrl+V` is allowed only when direct fill is unavailable and browser control can preserve verified composer focus continuously with no intervening yield.
- Added regression for the observed failure where a copied ChatGPT URL could land in Chrome's address bar and navigate away. The workflow must stop before paste/Enter instead.

## Reviewer language + private-repository protocol hotfix (2026-08-20)

- User <-> Antigravity communication remains in the user's language; when the user speaks Vietnamese, Antigravity should continue speaking Vietnamese to the user.
- Antigravity <-> ChatGPT Web reviewer communication is English-only for reviewer instructions, review reasoning, findings, test-gap analysis, and the machine-parseable final verdict.
- The deterministic delivery gate (`gh` + `pr_context.py`) is authoritative for OPEN PR identity and exact full HEAD SHA before prompt generation.
- Reviewer-side inability to open a private GitHub PR, including a 404 caused by reviewer-session permissions, is optional corroboration failure only and must not by itself force `NEEDS_HUMAN_DECISION`.
- The reviewer still fails closed for an internally inconsistent package, reliable evidence of a different HEAD, materially insufficient review evidence, or another substantive blocker.


### Reviewer transport optimization

Reviewer transport prioritizes direct DOM/field fill from `reviewer-prompt.txt`. If direct fill is unavailable, the automatic fallback now uses `paste_review_prompt.ps1`, which performs prompt validation, clipboard overwrite, exact clipboard read-back, clipboard-sequence stability check, and `Ctrl+V` inside one PowerShell process after the exact composer has been focused. Antigravity must never issue a blind/manual paste from the current clipboard. Every retry re-arms from the source file; repeated foreign clipboard payloads stop `BLOCKED` instead of looping. Post-paste composer readback remains authoritative before Send. Simulated typing remains disabled.


### Reviewer clipboard race hardening v2 (2026-08-20)
The Windows clipboard is treated as hostile shared state. A user copy action such as `House of Legacy PC` can no longer be reused across reviewer retries: direct-fill remains preferred, while clipboard fallback is a single-process `paste_review_prompt.ps1` operation that re-arms from `reviewer-prompt.txt` on every attempt. Foreign composer text triggers clear + fresh re-arm; the same foreign payload twice is a hard `BLOCKED` circuit-breaker.

### Reviewer attachment guard (2026-08-20)
Reviewer transport now verifies both exact prompt text and a zero-attachment composer surface. Screenshot/image/file clipboard races are fail-closed: any attachment or pending upload must be removed by clearing the entire draft and re-inserting from `reviewer-prompt.txt` before Send.


## MVP 1 external validation status — historical 2026-08-20

The 2026-08-20 build passed the then-current Windows/Antigravity flow. That transport has since been superseded. The active 2026-08-21 existing-browser-first review redesign requires a fresh Windows live validation before the current build may be declared externally PASS.


## MVP 2 C1 — Dedicated Architect

C1 activates an Architect only when deterministic classification sets `architect_required=true`. After Planner reaches `PLAN_READY`, the Architect produces `.ai/tasks/<task-id>/architecture.json` under `references/architect-contract.md`. Builder execution is blocked until this artifact validates. SIMPLE tasks bypass the Architect. The Architect does not edit production code by default and may escalate high-risk decisions to `HUMAN_DECISION`.


## C1 external validation hardening — 2026-08-20

C1 external validation PASS: SIMPLE bypass, COMPLEX Architect activation, Builder fail-closed ordering, durable `architecture.json`, high-risk human routing, exact-SHA review, and `RELEASE_GATE` were all validated on Windows/Antigravity.

Two validation-boundary rules were then hardened:

- PR identity for private repositories is verified with `gh` + `pr_context.py`; Antigravity must not open GitHub Web just to verify PR/HEAD, because an unauthenticated browser profile may legitimately return 404.
- Self-validation must not edit either the project-local `gemini-and-chatgpt/` source copy or `.agents/skills/gemini-and-chatgpt/` installed copy. Proof scripts, sample code, coverage and evidence belong outside the tool folders.


## MVP 2 C2 — Project Context v2

C2 adds deterministic repository discovery through `scripts/project_context_scan.py` and evolves `.ai/project-context.json` to schema `2.1.0`. For STANDARD/COMPLEX work, Antigravity now discovers normalized stack/language indicators, package managers/frameworks, project commands, key module topology, conventions, provenance and freshness metadata. SIMPLE tasks may bypass scanning to keep overhead low.

Context is fail-closed against staleness: source manifest/file signatures are fingerprinted; changed/missing/new provenance returns `STALE` and forces refresh before downstream roles consume it. Context can be requested by topic instead of dumping the full repository summary into prompts. `.env` values and other secrets are never stored; only variable names from example/sample/template env files are allowed. Tool folders, `.agents`, `.ai`, `.git`, dependencies, build outputs and caches are excluded from discovery.


### 2026-08-20 — C2 Project Context v2
- Added bounded repository scanner, provenance ledger, source fingerprint, freshness invalidation and lazy topic slices.
- Project context schema moves to `2.1.0`; legacy `2.0.0` context loads through an in-memory compatibility upgrade.
- STANDARD/COMPLEX classification automatically ensures fresh project context; recovery refreshes stale discovery.
- Secret-safe rules persist environment variable names only and exclude tool/runtime/dependency/build directories.


## 2026-08-20 — Clipboard-free reviewer transport

- Removed Windows clipboard/`Ctrl+V` from the active reviewer transport path after repeated real-world races with user clipboard activity.
- Historical note: this intermediate build still had a typed fallback. It is superseded by the active 2026-08-21 design below.
- Current normal flow has no typed fallback: DIRECT_FILL_CDP or `BLOCKED`.
- Full composer readback, exact SHA/PROMPT_ID verification, attachment guard, final target guard, timeout, and human-only release policy remain mandatory.


## Reviewer transport integrity hardening

Reviewer transport is protected by an immutable sidecar manifest. `review_prompt.py --output reviewer-prompt.txt` creates `reviewer-prompt.manifest.json` with canonical SHA256, character count, line count, PROMPT_ID, TARGET_HEAD_SHA, and full-package structure. DIRECT_FILL_CDP verifies this manifest before insertion and performs exact composer readback itself. Smoke tests must use separate fixture names; they must never overwrite the real reviewer package. Marker-only/truncated prompts fail closed.


### Direct-fill transport hardening (2026-08-20)

Reviewer transport has a clipboard-free path on Windows: Antigravity first uses its native browser capability to open/navigate its normal browser session to ChatGPT. `scripts/direct_fill_review_prompt.ps1` then discovers that already-running debuggable browser, preferring the Antigravity-owned process, and uses CDP `Input.insertText` to inject the complete immutable review package in one operation. This does not synthesize Enter key events. If no usable existing CDP endpoint exists, the transport fails closed and asks Antigravity to make its browser available; it never launches a separate reviewer Chrome/profile.

### Transport performance hotfix — one-shot verify + send (2026-08-20)
- DIRECT_FILL_CDP now owns the complete happy path in one PowerShell/CDP session: immutable package verification -> target/focus -> zero attachments -> full insert -> exact readback/hash -> final zero-attachment check -> Send click.
- Removed repeated Python verifier calls from the successful normal transport path; they remain diagnostics/fallback/regression tools.
- Normal review sends automatically. `-NoSend` is reserved only for explicit smoke tests.
- Any DIRECT_FILL failure other than exit code 3 stops fail-closed instead of entering long clear/retry loops.


## 2026-08-21 — Historical existing-browser/CDP reviewer + action logging (superseded)

The active design splits browser ownership from deterministic transport. Antigravity uses its native browser capability to open/navigate its normal signed-in browser session to ChatGPT. `review_round.py` owns the deterministic review operation after that point, and `direct_fill_review_prompt.ps1` attaches only to an already-running browser with a usable DevTools endpoint, preferring the Antigravity-owned process. It never launches/reuses a separate reviewer Chrome profile. The transport adopts one ChatGPT target that Antigravity already opened and reuses that same tab across rounds; it never creates a second ChatGPT tab, and navigates the adopted tab directly to `https://chatgpt.com/` instead of clicking `New chat`. Stale composer content is cleared through DOM state, never keyboard selection; a readback mismatch gets at most one in-place insertion retry, never a full `review_round.py` restart. Simulated typing remains removed. `review_round.py` also removes redundant GitHub calls by using one `gh pr view` plus a local exact-SHA `git diff`.

`orchestrator.py` and `review_round.py` now write `.ai/gemini-chatgpt-actions.log` plus structured `.jsonl` in-process. The log records meaningful command/action, PASS/FAIL, and duration without launching extra logger commands. Happy-path instructions explicitly forbid helper `--help`, repeated state reassurance checks, and standalone verifier calls after a consolidated step succeeds.


### Browser Subagent end-to-end review rule

The current Antigravity happy path uses one Browser Subagent task for the entire ChatGPT interaction. `prepare` returns immutable `reviewer-prompt.txt` plus `reviewer-browser-task.txt`. Main Agent reads the complete prompt with `view_file` and passes it verbatim to Browser Subagent. The subagent uses the native text-entry action actually exposed by its runtime; do not hard-code nonexistent helper names. Clipboard/paste remains disabled. Never press bare Enter while composing; use Shift+Enter only when a keystroke-oriented native input requires explicit line breaks. Before Send, verify the same composer draft contains both BEGIN and END markers, click Send exactly once, wait for generation to finish, and return the entire verbatim response. If the full prompt is already present, skip retyping and send it. A premature partial send is `BLOCKED`; do not send the remainder as a second message. The former `review_round.py transport` + PowerShell/CDP handoff is disabled.
