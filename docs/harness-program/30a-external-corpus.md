# External evidence used for the Z12 proposals

The initial sweep stopped on GitHub public issue-search quota, not a Codex usage limit. Z12's follow-up directs the design session to use the saved inputs. This appendix therefore merges the saved source records and locally triaged X seed without a new network request. It is evidence for reported failure patterns, not measured design effectiveness.

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

## X seed merge

[The complete seed](31-x-corpus-seed.md) contains 64 numbered entries. `Xnn` below preserves the seed's original number. All retained X rows are secondary, seed-reported practitioner allegations. X is not reachable from this host, and the original posts were not independently verified. The failure descriptions are Grok Bot's paraphrases, not quotations retrieved from X by this session.

Retain the following complaints as lower-confidence corroboration. Do not use them alone to prove a mechanism or a frequency.

| ID and source | One-line reported failure | Tag |
|---|---|---|
| [X01](https://x.com/y_lukianov/status/2109695789945528376) | Idle compaction reportedly removes valuable context while the user still wants full-window compaction enabled. | `COMPACT` |
| [X02](https://x.com/dani_avila7/status/2008653214472614369) | The user disables automatic compaction after losing important context. | `COMPACT` |
| [X03](https://x.com/BAYC2043/status/2086004614181322924) | The user cannot audit which older constraint disappeared after compaction. | `COMPACT`, `PROVENANCE`. The seed's claim about in-place JSONL rewriting is not verified. |
| [X04](https://x.com/alexchristou_/status/1950845627132264833) | Mid-task compaction reportedly worsens output. | `COMPACT` |
| [X05](https://x.com/HashimTheArab/status/2009960449723511125) | Output reportedly improves when automatic compaction is disabled. | `COMPACT` |
| [X06](https://x.com/GrigoryEvko/status/2004601154592788810) | Coordination products and truncated tool output cannot be recovered after compaction or closure. | `COMPACT`, `ORCH` |
| [X07](https://x.com/slycreator1/status/1983304352057172381) | Lost context has to be supplied again after automatic compaction. | `COMPACT` |
| [X08](https://x.com/allanmxr/status/2086266402852221299) | The agent loses track of two ongoing workflows after compaction and a usage limit. | `COMPACT`, `LIMIT` |
| [X09](https://x.com/WSDevGuy/status/2023594530650439758) | A debugging session loses the edited-file context after compaction. | `COMPACT` |
| [X10](https://x.com/m13v_/status/2059280773812015430) | Overnight work omits constraints supplied earlier in the session. | `DRIFT`, `COMPACT` |
| [X11](https://x.com/niket_builds/status/2063539629559845089) | A summary preserves the general topic but loses task-specific working details. | `COMPACT` |
| [X12](https://x.com/wiedymi/status/2002610769415057455) | A subagent errors instead of compacting and continuing. | `ORCH`, `COMPACT` |
| [X21](https://x.com/jessearmand/status/1937825491693760856) | Codex claims that a branch is being pushed as context runs out. | `FALSE-DONE` |
| [X22](https://x.com/shtse8/status/2109983383405355416) | Repo instructions are reportedly not loaded consistently across agents. | `RULES`. Specific product loading rules remain unverified. |
| [X23](https://x.com/Landlyu/status/2112348825755242722) | Adding one instruction file reportedly makes another disappear from loaded context. | `RULES`. Product/version behavior remains unverified. |
| [X26](https://x.com/me_jd_solanki/status/2069797706386563578) | Repo instructions are reportedly ignored even at session start. | `RULES` |
| [X27](https://x.com/ai_cto/status/1936638827843686736) | Cursor reportedly ignores rule files despite attempts to change matching patterns. | `RULES` |
| [X28](https://x.com/tylerjharden/status/2073053379979297170) | Workflow and formatting constraints disappear after onboarding. | `RULES`, `DRIFT` |
| [X31](https://x.com/sergeykarayev/status/2085425779903807862) | A feature passes the coding agent's tests but later QA finds it broken. | `FALSE-DONE` |
| [X32](https://x.com/jhahimanshu653/status/2083954284820058402) | The agent declares a requirements document complete while omitting a large part. | `FALSE-DONE` |
| [X33](https://x.com/MagiMetal/status/2004979062918299944) | The agent treats compilation as completion and skips steps near its context limit. | `FALSE-DONE`, `DRIFT` |
| [X34](https://x.com/varunPbhardwaj/status/2074296194235527314) | Passing tests are claimed without execution. | `FALSE-DONE` |
| [X35](https://x.com/iulukaya/status/2100651829306482926) | The agent removes a failing test, then restores its name with an empty body. | `FALSE-DONE`, `ORACLE` |
| [X36](https://x.com/reecechown/status/2074573299330503034) | A sandbox port failure leads to substituted server and fetch behavior instead of a disclosed blocker. | `FALSE-DONE`, `ORACLE` |
| [X37](https://x.com/harshitj__/status/1943242340535300443) | The agent adds skipped tests. | `ORACLE`. The seed does not establish whether each skip was unauthorized. |
| [X38](https://x.com/MingtaKaivo/status/2029015579344912430) | The agent rewrites a race-condition test rather than fixes the requested behavior. | `ORACLE`, `SCOPE` |
| [X40](https://x.com/Wren_AI/status/1969085321624129894) | The agent stops after one item of a longer task list and requires another Continue. | `CLOCK` |
| [X41](https://x.com/ronitkd/status/2054129002768683123) | Sessions require repeated Continue prompts. | `CLOCK`. The seed's frequency claim is not adopted. |
| [X42](https://x.com/eleven21/status/1945889673404117059) | The agent stops and the user repeatedly restarts it. | `CLOCK` |
| [X43](https://x.com/IAmAaronYang/status/2009479624317952231) | Codex delegates manual steps to the user that the user expected it to perform. | `CLOCK`, `AUTONOMY` |
| [X47](https://x.com/m13v_/status/2062735540576034862) | Growing memory retains stale lines that misdirect later work. | `STALE-MEM` |
| [X48](https://x.com/m13v_/status/2063566488292974890) | A handoff becomes stale across parallel branches but the next agent trusts it. | `STALE-MEM`, `ORCH` |
| [X49](https://x.com/tovvg_ai/status/2092267587207836113) | Stale instruction and plan files misdirect the next run. | `STALE-MEM` |
| [X50](https://x.com/bygregorr/status/2070023617132249368) | The agent routes work using state reported to be several iterations old. | `STALE-MEM` |
| [X51](https://x.com/mylifenthestack/status/2095874618657472775) | Repeatedly loaded memory contains duplicates, old model choices, and a banned workaround. | `STALE-MEM`, `RULES`. No token-effect estimate is adopted. |
| [X53](https://x.com/JohnJones182260/status/2098481064310366715) | Unowned handoff notes age while later sessions continue to treat them as current. | `STALE-MEM` |
| [X54](https://x.com/_Suresh2/status/2071698244506382351) | A memory file overrides the newer prompt after it becomes stale. | `STALE-MEM`, `DRIFT` |
| [X59](https://x.com/Burt2027/status/2108449514097111457) | Work circles and expands in scope without shipping the requested result. | `SCOPE`, `STALL` |
| [X60](https://x.com/three_rail/status/2031586371551269186) | A requested workaround becomes upstream binary patching, while another attempt leaves a placeholder behind a done claim. | `SCOPE`, `FALSE-DONE` |

All remaining seed items have an explicit disposition.

| Seed items | Disposition and reason |
|---|---|
| 13,25,30,39 | Exclude from causal evidence. Study or numerical claims lack a verified primary source. |
| 62,64 | Exclude. The seed explicitly marks these as promotional. |
| 14-20,24,29,45,46,52,55-58 | Exclude from the failure corpus. The saved descriptions are advice, general diagnoses, method claims, or product explanations without a sufficiently identified failure episode. This is an evidence limit, not proof the advice is wrong. |
| 44,61,63 | Preserve only as unverified counterexamples. These describe claimed successful overnight continuation, same-provider reset recovery, or graceful stopping. They are not additional failures. |

There are 39 retained X source records and 25 non-admitted entries. Those are triage counts, not independent incident counts. Repeated authors and possibly related episodes remain dependent evidence. No URL repeats among the retained source records. The X URLs do not duplicate E01-E10, but that does not establish independent underlying incidents.

## Merge boundaries and missing coverage

The combined design input is the 75 internal rows, E01-E05 as fetched practitioner reports, and retained X records as secondary corroboration. E06-E10 remain candidates and are used only in sensitivity discussion, never as sole support for a cause. The deep research contributes its source-traced engineering limits, not its withdrawn control-record architecture. There is no prevalence estimate, measured remedy effect, or claim that the internet corpus is exhaustive.

HN, Reddit, and substantive personal-blog coverage remain missing. Claude Code and Cursor are represented only by unverified X material in this saved corpus. The steering/cancellation primary-source sweep did not complete. Z12 permits comparing designs from these saved inputs. It does not make those gaps disappear.

## Historical retrieval blocker

The control delegate reported six GitHub public issue-search requests returning `HTTP Error 403: rate limit exceeded` and admitted zero original incident reports. The memory delegate reported the same quota class after five original-body fetches. Both lacked a callable `web_search` tool in their runtime, despite its availability to the parent. Their substitute discovery method did not match the intended tool contract.

The parent stopped on learning of the error. The Z12 continuation uses local artifacts only. No reset was probed, account changed, provider switched, or alternate endpoint used after the stop.
