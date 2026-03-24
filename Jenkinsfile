// =============================================================================
// movie-finder-backend — Jenkins declarative pipeline
//
// Stages:
//   1. Checkout Submodules
//   2. Lint (parallel)       — chain, imdbapi, app
//   3. Test (parallel)       — chain, imdbapi, app  (rag_ingestion excluded: needs real API keys)
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
                // Forward the SSH key so git can clone submodules over SSH.
                // Uses withCredentials + ssh-agent (no SSH Agent plugin required).
                withCredentials([sshUserPrivateKey(
                    credentialsId: 'github-ssh-key',
                    keyFileVariable: 'SSH_KEY'
                )]) {
                    sh '''
                        eval $(ssh-agent -s)
                        ssh-add "$SSH_KEY"
                        git submodule update --init --recursive
                        ssh-agent -k
                    '''
                }
                // Stash the complete workspace (main repo + submodules) so that
                // parallel stages running in separate @2/@3 workspaces can
                // unstash and get the full source tree.
                stash name: 'source', excludes: '.git,**/.git,**/.venv'
            }
        }

        // ------------------------------------------------------------------ //
        stage('Lint') {
            parallel {

                stage('Lint — chain') {
                    agent any
                    options { skipDefaultCheckout() }
                    steps {
                        unstash 'source'
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
                    options { skipDefaultCheckout() }
                    steps {
                        unstash 'source'
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
                    options { skipDefaultCheckout() }
                    steps {
                        unstash 'source'
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
                    options { skipDefaultCheckout() }
                    steps {
                        unstash 'source'
                        // ChainConfig requires these fields to instantiate (even in mocked tests).
                        // Values are dummy — no real API calls are made; all external clients
                        // are mocked in chain/tests/conftest.py.
                        sh """
                            docker run --rm \
                                -v "\$(pwd)":/workspace \
                                -w /workspace \
                                -e QDRANT_ENDPOINT=https://test.qdrant.io \
                                -e QDRANT_API_KEY=test-key \
                                -e OPENAI_API_KEY=sk-test-openai \
                                -e ANTHROPIC_API_KEY=sk-ant-test \
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
                            archiveArtifacts artifacts: 'chain-coverage.xml', allowEmptyArchive: true
                        }
                    }
                }

                stage('Test — imdbapi') {
                    agent any
                    options { skipDefaultCheckout() }
                    steps {
                        unstash 'source'
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
                            archiveArtifacts artifacts: 'imdbapi-coverage.xml', allowEmptyArchive: true
                        }
                    }
                }

                stage('Test — app') {
                    // Run on the Jenkins host (not inside a UV container) so we can
                    // manage Docker containers directly for the PostgreSQL sidecar.
                    agent any
                    options { skipDefaultCheckout() }
                    environment {
                        APP_SECRET_KEY = 'ci-test-only-not-a-real-secret' // pragma: allowlist secret
                        DATABASE_URL   = 'postgresql://postgres:postgres@ci-app-postgres:5432/movie_finder_test' // pragma: allowlist secret
                        CI_NET         = "ci-test-net-${env.BUILD_NUMBER}"
                    }
                    steps {
                        unstash 'source'
                        // Create an isolated bridge network so the UV container can
                        // reach the postgres container by hostname without conflicting
                        // with any pre-existing service on the host's port 5432.
                        sh 'docker network create "$CI_NET"'
                        sh '''
                            docker rm -f ci-app-postgres 2>/dev/null || true
                            docker run -d --name ci-app-postgres \
                                --network "$CI_NET" \
                                -e POSTGRES_PASSWORD=postgres \
                                -e POSTGRES_DB=movie_finder_test \
                                postgres:16-alpine
                            for i in $(seq 1 30); do
                                docker exec ci-app-postgres \
                                    pg_isready -U postgres -d movie_finder_test \
                                    && break || sleep 1
                            done
                        '''
                        sh """
                            docker run --rm \
                                --network "\$CI_NET" \
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
                            archiveArtifacts artifacts: 'app-coverage.xml', allowEmptyArchive: true
                            sh 'docker rm -f ci-app-postgres || true'
                            sh 'docker network rm "$CI_NET" || true'
                        }
                    }
                }

                // Test — rag_ingestion is intentionally excluded from CI.
                // Its tests make real OpenAI embedding API calls (no mock available)
                // and would incur cost on every pipeline run.

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
            agent any
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
            agent any
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
            // cleanWs requires a node context. With agent none at pipeline level,
            // we must allocate one explicitly.
            node('') {
                cleanWs()
            }
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
