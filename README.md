# Floor

**Every release raises the ceiling. Nobody watches the floor.**

Floor proves, for every release, who can still use it. It checks the CPU, memory and connectivity floors of a release and signs the result as an attestation. When a floor rises, an agent proposes a fix and the gate checks it again. Only a human can approve a release that leaves people behind.

Source project: [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (MIT). Built for the GitLab Transcend "Life After Code" hackathon (Path B, Hands-off).

## Status

Early development. The product requirements are in [docs/PRD.md](docs/PRD.md).

## Repository layout

| Path | Contents |
|---|---|
| `.floor/` | The Floor tools: Python package `floor`, tests, policy and schemas |
| `.floor/overrides/` | Build overrides that the repair agent may change |
| `docs/` | Product requirements and design notes |
| `scripts/` | Team scripts |

The project on GitLab is whisper.cpp at a pinned commit, plus the product files from this repository.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate            # Windows Git Bash: source .venv/Scripts/activate
pip install -e "./.floor[dev]"
python -m pytest .floor/tests -q
python -m floor scan path/to/binary-or-directory
```

## License

MIT. See [LICENSE](LICENSE).
