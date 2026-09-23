PY := .venv/bin/python

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	@echo "Now: cp .env.example .env and add your keys."

test:
	PYTHONPATH=src $(PY) -m pytest tests/ -q

retrieval-eval:
	$(PY) evals/run_retrieval_eval.py

eval-v0:
	$(PY) evals/run_eval.py --version v0

eval-v1:
	$(PY) evals/run_eval.py --version v1

judge:
	$(PY) evals/judge.py --results results/v1.json

demo:
	$(PY) evals/run_eval.py --version v1 --ids n09 a01 n06

.PHONY: setup test retrieval-eval eval-v0 eval-v1 judge demo
eval-v2:
	$(PY) evals/run_eval.py --version v2

