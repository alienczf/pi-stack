# Partial external evidence checkpoint

Blocked on 2026-10-23 by GitHub public issue-search quota. No Codex usage limit was observed. This file preserves links and short quotations collected before the stop. It is not the completed merged corpus, a cause analysis, or evidence that any design works.

Fetching an original complaint establishes what its author reported. It does not independently reproduce the failure. Closed issues below describe historical behavior and do not establish a current regression. No data dumps or full issue bodies are retained here.

## Parent-fetched original reports

The parent fetched these original issue bodies and comments through `fetch_content` after stages (a) and (b) completed. These five records are usable partial evidence. No incident below was reproduced locally.

| ID | Source and date | One-line failure reported by the practitioner | Short original quotation | Tag and qualification |
|---|---|---|---|---|
| E01 | [Goose #11072](https://github.com/aaif-goose/goose/issues/11072), created 2026-08-09. | A long autonomous tool turn crosses the context threshold without reevaluating compaction. | "A turn that begins under the threshold can run all the way to the provider's context limit without a single check." | `COMPACT`, `INNER-LOOP`. Body and comments fetched. Version-specific reports include session traces and independent confirmations. Closed at retrieval, not a claim about current Goose. |
| E02 | [Goose #10763](https://github.com/aaif-goose/goose/issues/10763), created 2026-07-28. | Clear and compact affect Goose's local conversation copy but not the ACP agent's actual context, while the displayed counter resets. | "The token counter is reset to zero at the same time" | `CONTROL`, `OBSERVATION`. Body and comments fetched. Reporter discloses a local build and comparison against upstream. Another commenter supplies a codex-acp trace. Closed at retrieval. |
| E03 | [LangGraph #6792](https://github.com/langchain-ai/langgraph/issues/6792), created 2026-02-12. | Wrapping an interrupting functional graph in a parent reportedly reruns a previously completed task and duplicates returned interrupts. | "now the task outputs are no longer being reused" | `ORCH`, `RETRY`. Body, example, output, and comments fetched. The shown example's invocation differs from its narrative. Later discussion distinguishes the nested-parent reproduction. Do not infer arbitrary duplicated external effects. |
| E04 | [Aider #4153](https://github.com/Aider-AI/aider/issues/4153), created 2025-06-02. | Architect mode repeatedly attempts search/replace when asked to remove a file. | "which will stop after 3 failed attempts but I stopped it manually" | `STALL`, `TOOL-LOOP`. Body and logs fetched. Aider 0.84.0. The issue's infinite-loop wording is stronger than the author's own finite-retry qualification. |
| E05 | [Aider #942](https://github.com/Aider-AI/aider/issues/942), corroborating comment dated 2025-02-15. | A watch-mode comment reportedly retriggers repeated edits even though the per-edit retry mechanism has its own limit. | "counted 23 search/replace attempts in a row" | `STALL`, `RETRIGGER`. Body and comments fetched. The maintainer asks for logs rather than accepts the initial infinite-loop assertion. A later commenter supplies a watch-mode account and logs. This does not prove that every retry crosses the same boundary. |

## Delegate-fetched candidates

The memory delegate reports separate HTTP-200 retrievals of these original issue bodies and metadata. The parent read its substantive report but did not refetch these pages after learning of the quota error. Comments and attachments remain unfetched. Collection timing relative to the initial premature workflow dispatch is not established in this checkpoint. Preserve them as candidates, not as admitted evidence in an ordered, deduplicated final corpus.

| ID | Source and creation date reported from metadata | One-line practitioner complaint | Short quote retained by the delegate | Tag and evidence limit |
|---|---|---|---|---|
| E06 | [Codex #43855](https://github.com/openai/codex/issues/43855), 2026-09-08. | After compaction, Codex stops the active task and asks what to do despite retaining repo rules and branch information. | "Basically codex works on a task and after compaction it just stops." | `COMPACT`, `CLOCK`. Codex CLI 0.153.4 with experimental context management. Referenced uploaded thread not inspected. |
| E07 | [Codex #31659](https://github.com/openai/codex/issues/31659), 2026-07-08. | A long-running goal reportedly returns to completed numbered-document prompts after auto-compaction. | "After the auto-compact, it will start to talk about the previous prompts, losing track of the goal." | `DRIFT`, `STALE-MEM`. Codex CLI 0.143.0. Personal reproduction claim, not an adopted failure rate. Screenshot and Git history not inspected. |
| E08 | [Aider #2219](https://github.com/Aider-AI/aider/issues/2219), 2024-11-01. | A practitioner reports invented material in summarized history and reconstructs working context manually. | "everything from the line 20 onwards seems to be a hallucinated waste of tokens." | `COMPACT`, `SUMMARY`. Attachment-dependent allegation. The author corrects an earlier assumption that the whole history was being sent. Do not repeat that retracted assumption. |
| E09 | [Cline #5616](https://github.com/cline/cline/issues/5616), 2025-08-16. | A large plan-to-act task repeatedly condenses and quickly refills the new conversation's context. | "After receiving a summary and starting a new chat, the new conversation within seconds has almost full context window as well" | `COMPACT`, `STALL`. Cline 3.25.2. The account does not identify an exact lost instruction. Closed metadata is not proof of a fix. |
| E10 | [Cline #5842](https://github.com/cline/cline/issues/5842), 2025-08-27. | A follow-up commit request reportedly restarts analysis of a task completed in the same session. | "starts analyzing the conversation repeatedly from beginning on and even starts solving problems that he just solved... (same session!)." | `STALE-MEM`, `REPEAT`. Cline 3.26.5. Much of the supplied explanation is pasted assistant self-analysis, not verified internal causation. No compaction trigger established for this event. |

The five delegate records have distinct upstream issue identifiers. E09 and E10 may share a nearby-version regression. No common incident has been established. A final merge still needs comment review and deduplication across the full external corpus.

## Counterevidence and exclusions already observed

[LangGraph #6663](https://github.com/langchain-ai/langgraph/issues/6663) was fetched with its comments. A practitioner expects different resumes of the same checkpoint to create independent branches. A maintainer replies, "This is the expected behavior, you're resuming w/ the same config :)". Do not count the report as a proved dropped cancellation or framework defect. It remains evidence of a caller-versus-resume-contract mismatch.

No source discovered only in search synthesis is promoted into the tables. No vendor marketing, repository launch pitch, or provider-switching product is admitted. No numerical claim about compaction fidelity, session failure frequency, or reviewer effectiveness is established here.

## X seed and missing coverage

[The complete X seed](31-x-corpus-seed.md) contains 64 numbered entries. The parent read it in full. It was a placeholder at dispatch and became complete during stages (a) and (b). X is not reachable from this host according to the program inputs. Original X posts were not independently verified here.

The seed still needs full per-item triage, deduplication, and merge. Its promotional exceptions, studies without a checked primary source, generic advice, and positive recovery accounts must not silently become failure evidence. In particular, seed items 13, 25, 30, and 39 make study or numerical claims requiring primary verification. Items 62 and 64 are explicitly promotional. Item 61 is a positive recovery account, not an additional stall.

HN, Reddit, substantive personal-blog coverage, Claude Code, Cursor, and a completed steering/cancellation sweep remain missing. The community delegate was stopped when the parent learned of the quota error. Its unfinished work is not admitted as a corpus or review.

## Retrieval blocker

The control delegate reports six GitHub public issue-search requests returning `HTTP Error 403: rate limit exceeded`. It admits zero original incident reports. The memory delegate reports the same quota class after its five original-body fetches. Both report that their runtime lacked a callable `web_search` tool, despite its availability to the parent. Their substitute discovery method therefore did not match the intended tool contract.

The parent learned of these errors on reading the actual reports and stopped further research under the program's quota rule. No model or provider was switched. No reset was probed, no account was changed, and no alternate endpoint was used after that observation.
