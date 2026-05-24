# GTM-OS Gallery

Browse, install, and compose GTM capabilities.

## Taxonomy

| Kind | Purpose | Drives outcome? | Has hypothesis? |
|------|---------|-----------------|-----------------|
| **Playbook** | Outcome-driven GTM experiment | Yes | Yes — goal, hypothesis, success metrics |
| **Workflow** | Reusable sequence of tasks | No — called by playbooks | No — just runs steps reliably |
| **Skill** | Atomic capability with embedded knowledge | No — called by workflows or playbooks | No — single-purpose |
| **Tool** | External utility integration | No — called by skills or workflows | No — just wraps an API or CLI |

## Dependency chain

```
Playbook (defines the outcome)
  └── calls Workflows (runs the steps)
        └── calls Skills (does the atomic work)
              └── calls Tools (wraps external systems)
```

## How it works

Each item is a YAML manifest with a standard `kind` field. The engine reads
these from `gallery/` and makes them available in the UI and via the API.

- **Playbooks** define `outcome`, `hypothesis`, `success_metrics`, and reference
  which `workflows`, `skills`, `tools`, and `knowledge` they need.
- **Workflows** define ordered `steps`, each calling a `tool` or `skill`.
- **Skills** define `input`, `output`, and embedded `knowledge`.
- **Tools** define `install`, `capabilities`, and `integration_pattern`.

## Installing to primitives

Playbooks can be installed as plays:

```bash
gtm-os gallery install <playbook-id>
# copies the playbook as a PLAY.md into primitives/plays/<id>/
```

## Directory layout

```
gallery/
├── playbooks/       # 14 outcome-driven experiments
├── workflows/       # 5 reusable task sequences
├── skills/          # 50+ atomic capabilities
├── tools/           # 10 external utility definitions
└── README.md
```
