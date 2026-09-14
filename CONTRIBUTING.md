# Contributing

Thanks for helping. A few rules keep crossbrain trustworthy:

1. **Run the gates:**
   ```bash
   python -m unittest discover -s scripts -p "test_*.py"
   python scripts/build_capabilities.py --check
   python scripts/preflight.py --staged
   ```
2. **Every new scanner check ships with fixtures:** one that must be caught, and one real-world string that must
   stay quiet. A gate that cries wolf gets disabled.
3. **Generic only.** Never commit anything specific to your own repositories: mined digests, `repo-*` skills,
   audit output, or client names. Those belong in your private brain pack.
4. **Harness paths come with a source.** If you add or change a tool's skills or instructions location, link
   its documentation in `docs/HARNESSES.md`.
5. **Commit subjects say why, not what.** Every PR states what was verified *and what was not*.

## Updating the vendored ECC library

```bash
python scripts/vendor_ecc.py --latest      # stages, scans, and only then swaps it in
python scripts/build_capabilities.py
```

Open a PR with the diff. Reviewers read new third-party instructions before they reach anyone's agents.
