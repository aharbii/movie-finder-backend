// =============================================================================
// movie-finder-backend — Jenkins declarative pipeline (integration CI)
//
// This pipeline lints and tests ALL workspace packages together, then builds
// the application Docker image. It runs against the full submodule tree.
//
// Triggers:
//   • PR validation  — every pull request to main
//   • Release        — every git tag matching v*
//   • Manual deploy  — Build with Parameters → check DEPLOY_STAGING
//
// Required Jenkins credentials:
//   docker-registry-url  — Docker registry base URL
//
// Required Jenkins plugins:
//   Docker Pipeline, JUnit, Cobertura, Credentials Binding, Git (submodules)
// =============================================================================

pipeline {
    agent none

    options {
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
        disableConcurrentBuilds(abortPrevious: true)
    }

    parameters {
        booleanParam(
            name: 'DEPLOY_STAGING',
            defaultValue: false,
            description: 'Deploy to staging environment after a successful build.'
        )
    }

    environment {
        SERVICE_NAME = 'movie-finder-backend'
        UV_IMAGE     = 'ghcr.io/astral-sh/uv:python3.13-bookworm-slim'
        DOCKER_IMAGE = 'docker:24-dind'
    }

    stages {

        // ------------------------------------------------------------------ //
        stage('Checkout Submodules') {
            agent { label 'any' }
            steps {
                // Ensure all submodules (imdbapi, rag_ingestion, chain) are present
                sh 'git submodule update --init --recursive'
            }
        }

        // ------------------------------------------------------------------ //
        stage('Lint') {
            parallel {

                stage('Lint — chain') {
                    agent {
                        docker {
                            image "${UV_IMAGE}"
                        }
                    }
                    steps {
                        sh 'uv sync --frozen --group lint'
                        sh 'uv run ruff check chain/src/ chain/tests/'
                        sh 'uv run ruff format --check chain/src/ chain/tests/'
                        sh 'uv run mypy chain/src/'
                    }
                }

                stage('Lint — imdbapi') {
                    agent {
                        docker {
                            image "${UV_IMAGE}"
                        }
                    }
                    steps {
                        dir('imdbapi') {
                            sh 'uv sync --frozen --group lint'
                            sh 'uv run ruff check src/ tests/'
                            sh 'uv run ruff format --check src/ tests/'
                            sh 'uv run mypy src/'
                        }
                    }
                }

            }
        }

        // ------------------------------------------------------------------ //
        stage('Test') {
            parallel {

                stage('Test — chain') {
                    agent {
                        docker {
                            image "${UV_IMAGE}"
                        }
                    }
                    steps {
                        sh 'uv sync --frozen --group test'
                        sh '''
                            uv run pytest chain/tests/ \
                                --cov=chain/src \
                                --cov-report=xml:chain-coverage.xml \
                                --junitxml=chain-test-results.xml \
                                -v --tb=short
                        '''
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'chain-test-results.xml'
                            cobertura coberturaReportFile: 'chain-coverage.xml',
                                      onlyStable: false,
                                      failNoReports: false
                        }
                    }
                }

                stage('Test — imdbapi') {
                    agent {
                        docker {
                            image "${UV_IMAGE}"
                        }
                    }
                    steps {
                        dir('imdbapi') {
                            sh 'uv sync --frozen --group test'
                            sh '''
                                uv run pytest tests/ \
                                    --cov=src \
                                    --cov-report=xml:imdbapi-coverage.xml \
                                    --junitxml=imdbapi-test-results.xml \
                                    -v --tb=short
                            '''
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'imdbapi/imdbapi-test-results.xml'
                        }
                    }
                }

                stage('Test — rag_ingestion') {
                    agent {
                        docker {
                            image "${UV_IMAGE}"
                        }
                    }
                    steps {
                        dir('rag_ingestion') {
                            sh 'uv sync --frozen --group test'
                            sh '''
                                uv run pytest tests/ \
                                    --cov=src \
                                    --cov-report=xml:rag-coverage.xml \
                                    --junitxml=rag-test-results.xml \
                                    -v --tb=short
                            '''
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'rag_ingestion/rag-test-results.xml'
                        }
                    }
                }

            }
        }

        // ------------------------------------------------------------------ //
        stage('Build App Image') {
            // Only on main or tagged releases
            when {
                anyOf {
                    branch 'main'
                    buildingTag()
                }
            }
            agent {
                docker {
                    image "${DOCKER_IMAGE}"
                    args '--privileged -v /var/run/docker.sock:/var/run/docker.sock'
                }
            }
            environment {
                DOCKER_REGISTRY = credentials('docker-registry-url')
                IMAGE_TAG = "${DOCKER_REGISTRY}/${SERVICE_NAME}:${env.GIT_TAG_NAME ?: env.GIT_COMMIT.take(8)}"
            }
            steps {
                sh "docker build -t ${IMAGE_TAG} ."
                sh "docker push ${IMAGE_TAG}"
                script {
                    if (env.BRANCH_NAME == 'main') {
                        sh "docker tag ${IMAGE_TAG} ${DOCKER_REGISTRY}/${SERVICE_NAME}:latest"
                        sh "docker push ${DOCKER_REGISTRY}/${SERVICE_NAME}:latest"
                    }
                }
            }
        }

        // ------------------------------------------------------------------ //
        stage('Deploy to Staging') {
            // Manual trigger only
            when {
                expression { params.DEPLOY_STAGING == true }
            }
            agent { label 'deploy' }
            environment {
                DOCKER_REGISTRY = credentials('docker-registry-url')
                IMAGE_TAG = "${DOCKER_REGISTRY}/${SERVICE_NAME}:${env.GIT_COMMIT.take(8)}"
            }
            steps {
                // TODO: Replace with your actual deploy script / Helm/kubectl command
                echo "Deploying ${IMAGE_TAG} to staging..."
                // sh './scripts/deploy.sh staging ${IMAGE_TAG}'
            }
        }

    }

    post {
        always {
            cleanWs()
        }
        failure {
            echo "Integration pipeline failed on branch ${env.BRANCH_NAME}."
        }
        success {
            script {
                if (buildingTag()) {
                    echo "Backend release ${env.GIT_TAG_NAME} built and pushed successfully."
                }
            }
        }
    }
}
