pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    // The server sits behind NAT, so there is nowhere for a webhook to arrive.
    triggers {
        pollSCM('H/5 * * * *')
    }

    environment {
        PATH+UV = '/var/lib/jenkins/.local/bin'
        PG_CONTAINER = 'redchair-ci-pg'
        DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5433/redchair_test'
        SECRET_KEY = 'test-secret-key-that-is-at-least-32-bytes'
        ALGORITHM = 'HS256'
        ACCESS_TOKEN_EXPIRE_MINUTES = '15'
    }

    stages {
        stage('Sync') {
            steps {
                sh 'uv sync --locked'
            }
        }

        stage('Lint') {
            steps {
                sh 'uv run ruff check .'
                sh 'uv run ruff format --check .'
                sh 'uv run mypy app'
            }
        }

        stage('Layer rules') {
            steps {
                // Services raise AppError subclasses and must not depend on the web layer.
                sh '''
                    if grep -rn fastapi app/services; then
                        echo "app/services must not import fastapi" >&2
                        exit 1
                    fi
                '''
                // Routers only speak HTTP; queries live in services.
                sh '''
                    if grep -rn sqlalchemy app/routers; then
                        echo "app/routers must not import sqlalchemy" >&2
                        exit 1
                    fi
                '''
            }
        }

        stage('Test DB') {
            steps {
                // A container left over from an aborted build would hold the name and the port.
                sh 'docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true'
                sh '''
                    docker run -d --rm --name "$PG_CONTAINER" \
                        -p 127.0.0.1:5433:5432 \
                        -e POSTGRES_PASSWORD=postgres \
                        -e POSTGRES_DB=redchair_test \
                        postgres:18
                '''
                // Probe over TCP: during init the entrypoint runs a socket-only server first.
                sh '''
                    i=0
                    while [ "$i" -lt 30 ]; do
                        if docker exec "$PG_CONTAINER" pg_isready -h 127.0.0.1 -U postgres -d redchair_test >/dev/null 2>&1; then
                            exit 0
                        fi
                        i=$((i + 1))
                        sleep 2
                    done
                    echo "postgres did not become ready" >&2
                    docker logs "$PG_CONTAINER" >&2 || true
                    exit 1
                '''
            }
        }

        stage('Migrations') {
            steps {
                sh 'uv run alembic upgrade head'
                sh 'uv run alembic downgrade base'
            }
        }

        stage('Tests') {
            steps {
                sh 'uv run pytest -q --junitxml=reports/junit.xml'
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
            sh 'docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true'
        }
    }
}
