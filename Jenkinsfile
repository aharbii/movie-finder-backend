// =============================================================================
// movie-finder-backend — Jenkins declarative pipeline
//
// Stages:
//   1. Checkout Submodules
//   2. Lint (parallel)       — chain, imdbapi, app
//   3. Test (parallel)       — chain, imdbapi, app, rag_ingestion
//   4. Build App Image       — main branch + v* tags + DEPLOY_STAGING=true
//   5. Deploy to Staging     — main branch (auto) or DEPLOY_STAGING=true
//   6. Deploy to Production  — v* tags only, after manual approval gate
//
// Triggers (configure in Jenkins job or via GitHub Branch Source plugin):
//   • Every PR to main
//   • Every push to main
//   • Every git tag matching v*
//   • Manual: Build with Parameters → check DEPLOY_STAGING
//
// Jenkins credentials required (Manage Jenkins → Credentials → Global):
//
//   Shared with the frontend pipeline (same service principal):
//   acr-login-server   Secret Text      Full ACR hostname, e.g. myacr.azurecr.io
//   acr-credentials    Username+Pass    SP App ID (user) + client secret (pass)
//                                       Used for "docker login" to ACR
//   azure-sp           Username+Pass    Same SP — used for "az login"
//                                       USR = App ID, PSW = client secret
//
//   Backend-specific:
//   azure-tenant-id    Secret Text      Azure Active Directory tenant ID
//   azure-sub-id       Secret Text      Azure subscription ID
//   aca-rg             Secret Text      Container Apps resource group name
//   aca-staging-name   Secret Text      Staging Container App name
//   aca-prod-name      Secret Text      Production Container App name
//
// Jenkins plugins required:
//   GitHub, Docker, JUnit, Cobertura, Credentials Binding, Git
//   Note: uses "docker run" in steps (not Docker Pipeline agent) so that
//   the Docker Pipeline plugin is NOT required.
//
// Jenkins agent labels required:
//   (none)  — build/test stages use "agent any" (any available executor)
//   deploy  — agent with Azure CLI (az) installed (for deploy stages)
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
            description: 'Force a staging deploy from any branch after a successful build.'
        )
    }

    environment {
        SERVICE_NAME = 'movie-finder-backend'
        UV_IMAGE     = 'ghcr.io/astral-sh/uv:python3.13-bookworm-slim'
    }

    stages {

        // ------------------------------------------------------------------ //
        stage('Checkout Submodules') {
            agent any
            steps {
                sh 'git submodule update --init --recursive'
            }
        }

        // ------------------------------------------------------------------ //
        stage('Lint') {
            parallel {

                stage('Lint — chain') {
                    agent any
                    steps {
                        sh """
                            docker run --rm \
                                -v "\$(pwd)":/workspace \
                                -w /workspace \
                                ${UV_IMAGE} \
                                sh -c 'uv sync --frozen --group lint && \
                                       uv run ruff check chain/src/ chain/tests/ && \
                                       uv run ruff format --check chain/src/ chain/tests/ && \
                                       uv run mypy chain/src/'
                        """
                    }
                }

                stage('Lint — imdbapi') {
                    agent any
                    steps {
                        sh """
                            docker run --rm \
                                -v "\$(pwd)":/workspace \
                                -w /workspace \
                                ${UV_IMAGE} \
                                sh -c 'uv sync --frozen --group lint && \
                                       uv run ruff check imdbapi/src/ imdbapi/tests/ && \
                                       uv run ruff format --check imdbapi/src/ imdbapi/tests/ && \
                                       uv run mypy imdbapi/src/'
                        """
                    }
                }

                stage('Lint — app') {
                    agent any
                    steps {
                        sh """
                            docker run --rm \
                                -v "\$(pwd)":/workspace \
                                -w /workspace \
                                ${UV_IMAGE} \
                                sh -c 'uv sync --frozen --group lint && \
                                       uv run ruff check app/src/ app/tests/ && \
                                       uv run ruff format --check app/src/ app/tests/ && \
                                       uv run mypy app/src/'
                        """
                    }
                }

            }
        }

        // ------------------------------------------------------------------ //
        stage('Test') {
            parallel {

                stage('Test — chain') {
                    agent any
                    steps {
                        sh """
                            docker run --rm \
                                -v "\$(pwd)":/workspace \
                                -w /workspace \
                                ${UV_IMAGE} \
                                sh -c 'uv sync --frozen --group test && \
                                       uv run pytest chain/tests/ \
                                           --cov=chain/src \
                                           --cov-report=xml:chain-coverage.xml \
                                           --junitxml=chain-test-results.xml \
                                           -v --tb=short'
                        """
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'chain-test-results.xml'
                            cobertura coberturaReportFile: 'chain-coverage.xml',
                                      onlyStable: false, failNoReports: false
                        }
                    }
                }

                stage('Test — imdbapi') {
                    agent any
                    steps {
                        sh """
                            docker run --rm \
                                -v "\$(pwd)":/workspace \
                                -w /workspace \
                                ${UV_IMAGE} \
                                sh -c 'uv sync --frozen --group test && \
                                       uv run pytest imdbapi/tests/ \
                                           --cov=imdbapi/src \
                                           --cov-report=xml:imdbapi-coverage.xml \
                                           --junitxml=imdbapi-test-results.xml \
                                           -v --tb=short'
                        """
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'imdbapi-test-results.xml'
                            cobertura coberturaReportFile: 'imdbapi-coverage.xml',
                                      onlyStable: false, failNoReports: false
                        }
                    }
                }

                stage('Test — app') {
                    // Run on the Jenkins host (not inside a UV container) so we can
                    // manage Docker containers directly for the PostgreSQL sidecar.
                    agent any
                    environment {
                        APP_SECRET_KEY = 'ci-test-only-not-a-real-secret' // pragma: allowlist secret
                        DATABASE_URL   = 'postgresql://postgres:postgres@localhost:5432/movie_finder_test' // pragma: allowlist secret
                    }
                    steps {
                        // Start a throwaway postgres container on the host network.
                        sh '''
                            docker run -d --name ci-app-postgres \
                                --network host \
                                -e POSTGRES_PASSWORD=postgres \
                                -e POSTGRES_DB=movie_finder_test \
                                postgres:16-alpine
                            for i in $(seq 1 30); do
                                docker exec ci-app-postgres \
                                    pg_isready -U postgres -d movie_finder_test \
                                    && break || sleep 1
                            done
                        '''
                        // Run tests inside the UV image; --network host lets it reach
                        // the postgres container at localhost:5432.
                        sh """
                            docker run --rm \
                                --network host \
                                -e APP_SECRET_KEY="\$APP_SECRET_KEY" \
                                -e DATABASE_URL="\$DATABASE_URL" \
                                -v "\$(pwd)":/workspace \
                                -w /workspace \
                                ${UV_IMAGE} \
                                sh -c 'uv sync --frozen --group test && \
                                       uv run pytest app/tests/ \
                                           --cov=app/src \
                                           --cov-report=xml:app-coverage.xml \
                                           --junitxml=app-test-results.xml \
                                           -v --tb=short'
                        """
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'app-test-results.xml'
                            cobertura coberturaReportFile: 'app-coverage.xml',
                                      onlyStable: false, failNoReports: false
                            sh 'docker stop ci-app-postgres && docker rm ci-app-postgres || true'
                        }
                    }
                }

                stage('Test — rag_ingestion') {
                    agent any
                    steps {
                        // rag_ingestion is NOT a workspace member — it has its own lockfile.
                        // Mount workspace root; cd into rag_ingestion inside the container.
                        sh """
                            docker run --rm \
                                -v "\$(pwd)":/workspace \
                                -w /workspace/rag_ingestion \
                                ${UV_IMAGE} \
                                sh -c 'uv sync --frozen --group test && \
                                       uv run pytest tests/ \
                                           --cov=src \
                                           --cov-report=xml:rag-coverage.xml \
                                           --junitxml=rag-test-results.xml \
                                           -v --tb=short'
                        """
                    }
                    post {
                        always {
                            junit allowEmptyResults: true,
                                  testResults: 'rag_ingestion/rag-test-results.xml'
                            cobertura coberturaReportFile: 'rag_ingestion/rag-coverage.xml',
                                      onlyStable: false, failNoReports: false
                        }
                    }
                }

            }
        }

        // ------------------------------------------------------------------ //
        stage('Build App Image') {
            when {
                anyOf {
                    branch 'main'
                    buildingTag()
                    expression { params.DEPLOY_STAGING == true }
                }
            }
            // Use the host Docker daemon directly — no DinD needed.
            agent any
            environment {
                ACR_SERVER = credentials('acr-login-server')
                // acr-credentials is a Username+Password credential (shared with frontend):
                //   ACR_CREDENTIALS_USR = service principal App ID
                //   ACR_CREDENTIALS_PSW = service principal client secret
                ACR_CREDENTIALS = credentials('acr-credentials')
            }
            steps {
                script {
                    // Derive image tag: git tag name for releases, short SHA otherwise
                    def tag = env.GIT_TAG_NAME ?: env.GIT_COMMIT.take(8)
                    env.BUILD_TAG  = tag
                    env.FULL_IMAGE = "${env.ACR_SERVER}/${env.SERVICE_NAME}:${tag}"
                }
                sh 'echo "$ACR_CREDENTIALS_PSW" | docker login "$ACR_SERVER" -u "$ACR_CREDENTIALS_USR" --password-stdin'
                // Pull :latest first so BuildKit can reuse unchanged layers (registry cache)
                sh "docker pull ${env.ACR_SERVER}/${env.SERVICE_NAME}:latest || true"
                sh """
                    docker build \
                        --cache-from ${env.ACR_SERVER}/${env.SERVICE_NAME}:latest \
                        -t ${env.FULL_IMAGE} \
                        .
                """
                sh "docker push ${env.FULL_IMAGE}"
                script {
                    // :latest is a convenience tag — never used directly by the deploy stages
                    if (env.BRANCH_NAME == 'main') {
                        def latestImage = "${env.ACR_SERVER}/${env.SERVICE_NAME}:latest"
                        sh "docker tag ${env.FULL_IMAGE} ${latestImage}"
                        sh "docker push ${latestImage}"
                    }
                }
            }
            post {
                always {
                    sh 'docker logout "$ACR_SERVER" || true'
                }
            }
        }

        // ------------------------------------------------------------------ //
        stage('Deploy to Staging') {
            when {
                anyOf {
                    branch 'main'
                    expression { params.DEPLOY_STAGING == true }
                }
            }
            // This agent must have the Azure CLI (az) installed.
            // Install: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli
            agent { label 'deploy' }
            environment {
                // azure-sp is shared with the frontend (Username+Password):
                //   AZURE_SP_USR = SP App ID, AZURE_SP_PSW = client secret
                AZURE_SP        = credentials('azure-sp')
                AZURE_TENANT_ID = credentials('azure-tenant-id')
                AZURE_SUB_ID    = credentials('azure-sub-id')
                ACA_RG          = credentials('aca-rg')
                ACA_NAME        = credentials('aca-staging-name')
                ACR_SERVER      = credentials('acr-login-server')
            }
            steps {
                sh '''
                    az login --service-principal \
                        --username "$AZURE_SP_USR" \
                        --password "$AZURE_SP_PSW" \
                        --tenant   "$AZURE_TENANT_ID"
                    az account set --subscription "$AZURE_SUB_ID"
                '''
                sh '''
                    az containerapp update \
                        --name           "$ACA_NAME" \
                        --resource-group "$ACA_RG" \
                        --image          "$ACR_SERVER/$SERVICE_NAME:$BUILD_TAG"
                    az containerapp revision list \
                        --name           "$ACA_NAME" \
                        --resource-group "$ACA_RG" \
                        --output         table
                '''
            }
            post {
                always {
                    sh 'az logout || true'
                }
            }
        }

        // ------------------------------------------------------------------ //
        stage('Deploy to Production') {
            // Only triggered by a versioned git tag (e.g. v1.2.3).
            // Requires a human to click "Deploy" in the Jenkins UI.
            when { buildingTag() }
            agent { label 'deploy' }
            environment {
                AZURE_SP        = credentials('azure-sp')
                AZURE_TENANT_ID = credentials('azure-tenant-id')
                AZURE_SUB_ID    = credentials('azure-sub-id')
                ACA_RG          = credentials('aca-rg')
                ACA_NAME        = credentials('aca-prod-name')
                ACR_SERVER      = credentials('acr-login-server')
            }
            steps {
                // Manual approval gate — times out after 30 min if no response
                timeout(time: 30, unit: 'MINUTES') {
                    input message: "Deploy ${env.GIT_TAG_NAME} to PRODUCTION?",
                          ok: 'Deploy',
                          submitter: 'release-managers'
                }
                sh '''
                    az login --service-principal \
                        --username "$AZURE_SP_USR" \
                        --password "$AZURE_SP_PSW" \
                        --tenant   "$AZURE_TENANT_ID"
                    az account set --subscription "$AZURE_SUB_ID"
                '''
                sh '''
                    az containerapp update \
                        --name           "$ACA_NAME" \
                        --resource-group "$ACA_RG" \
                        --image          "$ACR_SERVER/$SERVICE_NAME:$BUILD_TAG"
                    az containerapp revision list \
                        --name           "$ACA_NAME" \
                        --resource-group "$ACA_RG" \
                        --output         table
                '''
            }
            post {
                always {
                    sh 'az logout || true'
                }
            }
        }

    }

    post {
        always {
            cleanWs()
        }
        failure {
            echo "Pipeline failed on ${env.BRANCH_NAME ?: env.GIT_TAG_NAME ?: 'unknown ref'}."
        }
        success {
            script {
                if (buildingTag()) {
                    echo "Release ${env.GIT_TAG_NAME} (${env.BUILD_TAG}) deployed to production."
                } else if (env.BRANCH_NAME == 'main') {
                    echo "Build ${env.BUILD_TAG} deployed to staging."
                } else {
                    echo "CI passed for ${env.BRANCH_NAME}."
                }
            }
        }
    }
}
