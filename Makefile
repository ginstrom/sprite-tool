.PHONY: test check

test:
	uv run pytest

check: test
