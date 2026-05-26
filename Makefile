.PHONY: install dev api web test backtest fmt lint docker-up docker-down

install:
	python -m pip install -e ".[dev,backtest]"
	cd frontend && npm install

api:
	uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd frontend && npm run dev

dev:
	@echo "Run 'make api' and 'make web' in two terminals."

test:
	pytest -q

backtest:
	python -m backend.app.backtest.runner --strategy balanced

fmt:
	ruff format backend
	cd frontend && npm run format || true

lint:
	ruff check backend

docker-up:
	docker compose up --build

docker-down:
	docker compose down
