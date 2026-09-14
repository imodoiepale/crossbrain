# Supported agent CLIs

harnessd installs **Agent Skills** (a folder containing `SKILL.md` with `name` + `description` frontmatter), which
is the open format these tools share. It writes to two global folders by default. Between them, those two folders reach every tool below:

| Folder | Read by |
|---|---|
| `~/.claude/skills` | Claude Code, OpenCode, Kimi Code |
| `~/.agents/skills` | Codex, Cursor, Gemini CLI, OpenCode, Kimi Code |

Add more targets with `harnessd config skill_targets '["claude","agents","cursor"]'`.

## Per tool

| Tool | Global skills | Global instructions (`harnessd` block) | Session hook | Source |
|---|---|---|---|---|
| **Claude Code** | `~/.claude/skills` | `~/.claude/CLAUDE.md` | ✅ SessionStart brain card | Claude Code docs |
| **Codex** | `~/.agents/skills` (also `~/.codex/skills`) | `~/.codex/AGENTS.md` | — | [Codex customisation](https://codex.danielvaughan.com/2026/04/12/codex-cli-customisation-stack-unified-system/) |
| **Cursor** | `~/.agents/skills`, `~/.cursor/skills` | UI only (Settings → Rules) | — | [Cursor skills](https://cursor.com/docs/skills) |
| **Gemini CLI** | `~/.gemini/skills` or `~/.agents/skills` | `~/.gemini/GEMINI.md` | — | [Gemini CLI skills](https://geminicli.com/docs/cli/skills/) |
| **OpenCode** | `~/.config/opencode/skills`, `~/.claude/skills`, `~/.agents/skills` | `~/.config/opencode/AGENTS.md` (opt-in, see below) | — | [OpenCode skills](https://opencode.ai/docs/skills/), [rules](https://opencode.ai/docs/rules/) |
| **Kimi Code** | `~/.kimi/skills` or `~/.claude/skills`; `~/.config/agents/skills` or `~/.agents/skills` | not documented | — | [Kimi Code skills](https://moonshotai.github.io/kimi-cli/en/customization/skills.html) |

Paths were checked against each tool's documentation in September 2026. Tools change, so if one of these is out of date, please
open an issue.

## Things worth knowing

- **Instruction files are only touched where the tool already has a config folder.** harnessd never creates
  `~/.gemini/` just to write a `GEMINI.md`. Everything outside its marked block is left untouched:
  ```
  <!-- harnessd:begin --> … <!-- harnessd:end -->
  ```
- **OpenCode instructions are opt-in.** OpenCode reads `~/.claude/CLAUDE.md` *only when* `~/.config/opencode/AGENTS.md`
  does not exist. Creating that file by default would silently drop your Claude rules from OpenCode. Enable it
  with `harnessd config instruction_targets '["claude","codex","gemini","opencode"]'`.
- **Duplicates.** OpenCode and Kimi Code read both default folders, so each skill exists twice on disk for them.
  If a tool lists a skill twice, set `skill_targets` to the single folder that tool needs.
- **Session hooks are Claude Code only.** Other tools get the same routing through their instruction file and the
  `brain` skill, but without the automatic per-repo card at session start.
- **Subagents.** The vendored ECC reviewer agents install into `~/.claude/agents`. Other tools can use the same
  briefs by reading `vendor/ecc/agents/<name>.md`, and `capabilities` tells them where those files are.
