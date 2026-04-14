SHELL := /usr/bin/env bash

# Strip any leaked virtualenv vars so poetry always resolves to this project's
# venv — not whatever venv the parent shell happens to have activated.
POETRY := env -u VIRTUAL_ENV -u POETRY_ACTIVE poetry

GUARD_DIR := guards
INSTALL   := $(GUARD_DIR)/install.sh
UNINSTALL := $(GUARD_DIR)/uninstall.sh
TEST      := $(GUARD_DIR)/test-guard.sh
DENYLIST  := $(GUARD_DIR)/denylist.txt
SETTINGS  := $(HOME)/.claude/settings.json
LOG       := $(HOME)/.claude/guards/blocked.log

.DEFAULT_GOAL := help

.PHONY: help install uninstall reinstall test denylist settings log log-tail log-clear status clean deps sandbox sandbox-list gain test-py

help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Register the PreToolUse hook in ~/.claude/settings.json
	@$(INSTALL)

uninstall: ## Remove the hook from ~/.claude/settings.json
	@$(UNINSTALL)

reinstall: uninstall install ## Uninstall then install

test: ## Smoke-test denylist patterns against sample commands
	@$(TEST)

denylist: ## Open the denylist in $$EDITOR
	@$${EDITOR:-vi} $(DENYLIST)

settings: ## Show the hooks block of ~/.claude/settings.json
	@python3 -c 'import json,sys; print(json.dumps(json.load(open("$(SETTINGS)")).get("hooks",{}), indent=2))'

log: ## Print the full blocked-command log
	@[ -f $(LOG) ] && cat $(LOG) || echo "(no blocks logged yet: $(LOG))"

log-tail: ## Tail the blocked-command log
	@mkdir -p $(dir $(LOG)) && touch $(LOG) && tail -f $(LOG)

log-clear: ## Delete the blocked-command log
	@rm -f $(LOG) && echo "cleared $(LOG)"

status: ## Show whether the hook is currently registered
	@python3 -c 'import json,os,sys; \
	p=os.path.expanduser("$(SETTINGS)"); \
	d=json.load(open(p)) if os.path.exists(p) else {}; \
	pre=d.get("hooks",{}).get("PreToolUse",[]); \
	hits=[h["command"] for e in pre for h in e.get("hooks",[]) if "cmd-guard.sh" in h.get("command","")]; \
	print("registered:" if hits else "NOT registered"); \
	[print(" ",c) for c in hits]'

deps: ## Install project dependencies with poetry
	@$(POETRY) install

sandbox-list: ## List registered adversarial probes
	@$(POETRY) run sandbox --list

sandbox: ## Run the adversarial sandbox (override vars: N=3 PROBES=direct,polite)
	@$(POETRY) run sandbox --n $${N:-1} $${PROBES:+--probes $$PROBES}

gain: ## Summarize blocked-command history (override: ARGS="--since 7d")
	@$(POETRY) run gain $${ARGS}

test-py: ## Run the python unit tests
	@$(POETRY) run pytest tests/ -v

clean: ## Remove Python caches and build artefacts
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@rm -rf dist build *.egg-info
