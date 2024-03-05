include .env
export

run:
	poetry run uvicorn schema:app --reload

fmt:
	ruff check -s --fix --exit-zero .

lint list_strict:
	mypy .
	ruff check .

lint_fix: fmt lint

migrate:
	poetry run python -m yoyo apply -vvv --batch --database "postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB_NAME}" ./migrations

docker-services-up:
	docker-compose -f docker/docker-compose.yaml up

create-db:
	docker-compose -f docker/docker-compose.yaml exec postgres psql -U ${POSTGRES_USER} -c "CREATE DATABASE \"${POSTGRES_DB_NAME}\";"

drop-db:
	docker-compose -f docker/docker-compose.yaml exec postgres psql -U ${POSTGRES_USER} -c "DROP DATABASE \"${POSTGRES_DB_NAME}\";"

docker-services-down:
	docker-compose -f docker/docker-compose.yaml down