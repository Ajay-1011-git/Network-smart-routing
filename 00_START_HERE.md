# SmartRoute AI — maximum two Codex sessions

This pack reviews and amends the supplied SmartRoute guide and gives two persistent Codex sessions enough instructions to finish a local research demonstrator. It does not contain a finished application. No existing SmartRoute implementation repository was supplied or inspected.

## Use the pack

1. Extract this folder. Read `01_REVIEW_AND_REUSE.md` for the decisions and evidence.
2. Create or open your project repository. Copy the **contents** of `starter/` to its root, preserving `src/smartroute/`. Put this pack's Markdown documents in `docs/build/`. Keep the original guide for background.
3. Give Session A `SESSION_A_ENGINE.md`, `02_SHARED_SPEC.md`, and the project repository. Its first task is bootstrap and a shared-base commit.
4. After that commit exists, open Session B in a **separate checkout/worktree** of the same base. Give it `SESSION_B_INTELLIGENCE_AND_UI.md` and `02_SHARED_SPEC.md`. It can begin with fixtures while A completes the engine.
5. Keep both sessions alive. A sends its engine-ready commit; B merges that commit, generates real training data, trains and benchmarks, and finishes the dashboard. A then merges B and runs final acceptance. Fixes stay with these same two sessions. No third integration session is needed.

“Two sessions” here means at most two persistent coding conversations, each able to take follow-up messages. It does not promise completion in two one-shot responses or a fixed number of hours. If only sequential sessions are possible, finish A's engine-ready milestone first; B then owns final integration using the same acceptance checklist. The parallel setup is the default.

## Copy into Session A

> Implement SmartRoute AI using docs/build/SESSION_A_ENGINE.md and docs/build/02_SHARED_SPEC.md. Read the repository and applicable AGENTS.md first. Execute A0 through A6, then remain the integration owner for A7 when Session B's commit arrives. Use the supplied audited ns.py components; inspect their exact behavior before wrapping them. Do not rewrite their FIFO/serialization logic. Commit a working bootstrap first so Session B can branch from it. Keep work within your ownership, run actual checks, and finish all authorized work without routine confirmation pauses. Report the bootstrap and engine-ready commit hashes. Maximum two Codex sessions in total: do not spawn additional agents or require another integration session.

## Copy into Session B

> Implement SmartRoute AI using docs/build/SESSION_B_INTELLIGENCE_AND_UI.md and docs/build/02_SHARED_SPEC.md. Read the repository and applicable AGENTS.md first. Execute B0 through B6 on the bootstrap base from Session A. Use the shared contracts verbatim. Start with explicitly labeled fixtures; merge A's engine-ready commit before real data generation, training, and benchmarks. Own forecasting, predictive routing, experiments, and Streamlit/Plotly UI. Do not rewrite the engine or metrics. Send A your final commit and evidence; resolve defects in your owned files in this same session. Maximum two Codex sessions in total: do not spawn additional agents. Continue until your acceptance checklist passes.

## Two useful handoff messages

A → B: `Bootstrap <SHA>; engine-ready <SHA>; setup <commands>; trace <hash>; checks <real output>; known issues <list>. Merge engine-ready before generating data.`

B → A: `Final <SHA>; model <artifact/hash>; split manifest <path/hash>; benchmark manifest <path/hash>; checks <real output>; remaining failures <list>. Merge and run A7.`

## Final product

A local Python simulator, static/reactive/predictive policies, reproducible packet traces, trained forecasting model, fair benchmark report, and a dashboard with topology replay, route explanations, forecast accuracy, policy comparison, and exports. No paid API, GPU, ns-3, C++ build, or cloud service is required by this design. Installation still needs access to the chosen package sources or pre-cached dependencies.

The recommended scope uses Streamlit instead of React/FastAPI to fit the session cap. That is a deliberate amendment to the original guide's optional UI stack. The supplied starter contains only an immutable contract, three reused upstream components with their license, and three reuse smoke tests.
