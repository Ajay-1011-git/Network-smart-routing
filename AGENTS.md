# SmartRoute implementation

Direct user instructions take precedence over docs/build/02_SHARED_SPEC.md, then session plans.
Preserve src/smartroute/contracts.py verbatim. Reuse the supplied Port/Wire service logic.
Do not spawn agents. This build is being implemented sequentially in one conversation;
the original A/B directory ownership describes module boundaries, not a requirement to open chats.
Engine/baselines own simulation and metrics. Intelligence imports the shared scorer.
Dashboard and experiments call the SDK; never implement alternate metrics or a fake engine.
Generated large files belong in ignored artifacts/. Keep a compact trusted model in models/.
Run analytic tests, the causal feature tests and the paired benchmark audit before claiming completion.

