# Submission validation

Prepared from the Desktop submission archive on 2026-10-27. The original ZIP is preserved. Its previous Git metadata and compiled Python caches were not imported. This repository starts with a fresh history and includes the application, hash locks, tests and setup instructions.

## Local checks

- Python unit tests: 14 passed.
- JavaScript unit tests: 8 passed.
- Launcher help and module syntax checks: passed.
- Git whitespace, repository integrity and clean-worktree checks: passed before handoff.
- Source and initial commit scanned for the previously supplied provider credential, common secret patterns, private filesystem paths and private tooling files: none included. Fake test credentials are intentional. No credential files or environment files are included. The launcher takes the key through a hidden interactive prompt and does not persist it.
- No remote configured or pushed. No dependencies or models downloaded for validation.

The included CI workflow runs Python and JavaScript tests on Linux and Windows after pushing to GitHub. Remote CI has not run yet. No API key is needed by these tests.

## Runtime evidence and limits

The earlier Mac live test used local Qwen generation with a separate DeepSeek judge and completed a check-in after native verification scored 0.95. This Desktop archive instead configures DeepSeek Pro generation and DeepSeek Flash verification. That all-cloud configuration has unit-test coverage; a real paid end-to-end acceptance run on this exact tree remains unverified. No previous run's verdict is presented as proof for this configuration.

DeepSeek's official API documentation lists `deepseek-v4-pro` and `deepseek-flash`, and accepts the legacy Flash alias used by Nightshift's pinned catalog: https://api-docs.deepseek.com/ . Catalog alias metadata is normalized by the relay; original provider responses are retained in runtime evidence. Native grading and verdict logic are not overridden.

The server still runs locally. An online deployment requires hosting and a backend-held credential. Zetaris/H-MEM remain local mirrors. No hackathon submission has been made.

The launcher key-prompt behavior is tested, including refusal of noninteractive input and empty keys. No paid provider requests were made while preparing this revision.
