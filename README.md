# Little Jahsi × Nightshift

Little Jahsi turns a user's goal into a plan using real Nightshift generation and independent verification. Accepted plans continue into the original check-in, memory and progress flow. Rejected plans stay visible for review.

## Start the demo

Requirements: Python 3.10+, curl, internet access, a DeepSeek API key, and a modern browser. Node 24+ is optional, for JavaScript tests only. No Python packages, Ollama installation, or local model downloads are required for DeepSeek mode.

1. Open an interactive terminal in this repository folder.
2. Start the demo and enter your own DeepSeek key when the hidden prompt appears:

   ```powershell
   py -3 meterless_nightshift_lab/lab.py start --deepseek
   ```

   The key is kept only in server memory for this session. No credential file or environment variable is needed. It is never added to Git or passed as a command-line argument.

3. Open http://127.0.0.1:8765/graduation-loop.html and refresh after restarting the launcher.
4. Choose **Speak up**, enter “Tomorrow I want to ask one clarifying question about the material in my class.”, choose **1 week**, and select **Begin my journey**.
5. Show the actual generated plan, verifier verdict and receipt. Once accepted, continue to the check-in, record the outcome and reflection, and show saved memory and progress.

Keep the terminal open while using the demo. Press Ctrl+C to stop it. The session cap allows eight paid API calls. A one-candidate job normally uses generation and judging calls; retries or extra engine requests may use more.

For optional local-only mode without a DeepSeek key, install Ollama, run `py -3 meterless_nightshift_lab/lab.py setup-models` once, then start without `--deepseek`.

## How it works

DeepSeek V4 Pro generates the plan and DeepSeek V4 Flash independently judges it through Nightshift's normal `meterless-proxy` provider and `verifier_panel`. Supported quality mode uses one candidate, a rubric frozen before generation and the unchanged native 0.85 threshold. The relay only transports requests and responses; it does not assign scores or override verdicts.

The API key stays in the Python process. The goal, rubric and draft go to DeepSeek; check-in reflections remain in the browser. The explicit `--deepseek` flag enables paid generation and judging, capped at eight API calls per launcher session. Without that flag, the launcher uses local generation and verification. The browser can download actual run evidence, including the answer, verdict and receipt.

A Mac browser acceptance test completed the earlier local-model flow: score 0.95, accepted plan, check-in recorded, memory updated and 28% journey progress. The all-DeepSeek cloud path is a separate configuration and must be run on the target machine before claiming it passed. Future model verdicts may differ. The receipt is unsigned; cost fields are estimates. Progress after one check-in is not graduation.

## Tests

```sh
PYTHONPATH=meterless_nightshift_lab python3 -m unittest discover -s meterless_nightshift_lab/tests -p 'test_*.py'
node --test meterless_nightshift_lab/tests/*.mjs
```

On Windows PowerShell, run:

```powershell
$env:PYTHONPATH = "meterless_nightshift_lab"
py -3 -m unittest discover -s meterless_nightshift_lab/tests -p "test_*.py"
npm test
```

On macOS/Linux, use `python3` instead of `py -3` in the startup command. No npm install is needed for these tests.

## Prepare a remote

This is a standalone source repository on branch `main`. Once you create an empty remote repository, connect it and push:

```sh
git remote add origin "YOUR_REMOTE_URL"
git push -u origin main
```

No credential files are included or required. Enter your own key at the hidden startup prompt. This source package contains no provider key, private run records, model weights or previous Git history. See [validation notes](VALIDATION.md) for the exact checks and remaining runtime limits.

## Upstream sources and scope

The launcher downloads hash-pinned public Nightshift assets from https://meterless.ai/Nightshift/WEB/ and the founder's original interface from https://github.com/jahsistjohn1-a11y/little-jahsi-graduation-loop at the revision in `little_jahsi.lock.json`. Upstream assets retain their respective owners' terms. This package does not redistribute downloaded assets or model weights.

This is a local working demonstration. An optional real Zetaris SQL context connection is available through `--zetaris`; see [Zetaris setup and evidence](ZETARIS.md). A real query must succeed before claiming it is connected. H-MEM and check-in memory remain local. Public deployment and HackOS submission are separate steps.
