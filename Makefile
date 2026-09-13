.PHONY: test evaluate train docker-build docker-up

test:
	python -m pytest tests/ -v

# Reads the committed model bundle + sidecar -- no database or API keys needed.
# To retrain from live data: make train  (requires .env with Neon DB credentials)
evaluate:
	mkdir -p reports
	python scripts/report_model_eval.py

train:
	python -m src.ml.train

docker-build:
	docker build -t operations-performance .

docker-up:
	docker compose up --build
