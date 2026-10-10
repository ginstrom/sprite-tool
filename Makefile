.PHONY: test check golden

test:
	uv run pytest

check: test
	uv run sprite check --project examples/demo

# Rebuild the demo and replace tests/golden/ with its output. Run this only
# when a change to generated files is intended, and review the diff.
golden:
	uv run sprite build --project examples/demo
	rm -rf tests/golden
	mkdir -p tests/golden
	cp -R examples/demo/out/. tests/golden/
