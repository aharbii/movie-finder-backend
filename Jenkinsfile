// =============================================================================
// movie-finder-backend — Jenkins declarative pipeline
//
// Stages:
//   1. Checkout Submodules
//   2. Lint + Typecheck — backend app
//   3. Test — backend app (PostgreSQL via docker-compose)
//   4. Build App Image
//   5. Deploy to Staging
//   6. Deploy to Production
//
// Iteration boundary:
//   This pipeline currently validates the backend-owned app slice only. The
//   child repo Docker/task rollouts are tracked independently in:
//     - movie-finder-chain#9
//     - imdbapi-client#3
//     - movie-finder-rag#13
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
//   aca-staging-rg     Secret Text      Staging Container App resource group
//   aca-staging-name   Secret Text      Staging Container App name
//   aca-prod-rg        Secret Text      Production Container App resource group
//   aca-prod-name      Secret Text      Production Container App name
//
// Jenkins plugins required:
//   GitHub, Docker, JUnit, Credentials Binding, Git
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
    }

    stages {

        // ------------------------------------------------------------------ //
        stage('Checkout Submodules') {
            agent any
            steps {
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
                // Stash the complete workspace so later stages can run on any
                // executor with the full repo + submodule checkout.
                stash name: 'source', excludes: '.git,**/.git,**/.venv,**/htmlcov,**/*.xml'
            }
        }

        // ------------------------------------------------------------------ //
        stage('Lint + Typecheck — backend app') {
            agent any
            options { skipDefaultCheckout() }
            steps {
                unstash 'source'
                sh '''
                    set -e
                    export COMPOSE_PROJECT_NAME="movie-finder-backend-ci-${BUILD_NUMBER}"
                    make init
                    make lint
                    make typecheck
                '''
            }
            post {
                always {
                    sh '''
                        export COMPOSE_PROJECT_NAME="movie-finder-backend-ci-${BUILD_NUMBER}"
                        make ci-down || true
                    '''
                }
            }
        }

        // ------------------------------------------------------------------ //
        stage('Test — backend app') {
            agent any
            options { skipDefaultCheckout() }
            environment {
                APP_SECRET_KEY = 'ci-test-only-not-a-real-secret' // pragma: allowlist secret
                OPENAI_API_KEY = 'sk-test-openai' // pragma: allowlist secret
                ANTHROPIC_API_KEY = 'sk-ant-test' // pragma: allowlist secret
                QDRANT_URL = 'https://test.qdrant.io' // pragma: allowlist secret
                QDRANT_API_KEY_RO = 'test-key' // pragma: allowlist secret
                QDRANT_COLLECTION_NAME = 'movies'
            }
            steps {
                unstash 'source'
                sh '''
                    set -e
                    export COMPOSE_PROJECT_NAME="movie-finder-backend-ci-${BUILD_NUMBER}"
                    # Compose publishes host ports even for dependency services, so
                    # keep them unique per build to avoid collisions on shared agents.
                    export POSTGRES_HOST_PORT="$((54320 + BUILD_NUMBER % 1000))"
                    export BACKEND_HOST_PORT="$((55320 + BUILD_NUMBER % 1000))"
                    export TEST_DATABASE_URL="postgresql://movie_finder:devpassword@postgres:5432/movie_finder_test" # pragma: allowlist secret
                    make init
                    docker compose run --rm \
                        -e DATABASE_URL="$TEST_DATABASE_URL" \
                        backend pytest app/tests/ \
                            --cov=app \
                            --cov-report=xml:app-coverage.xml \
                            --junitxml=app-test-results.xml \
                            -v --tb=short
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'app-test-results.xml'
                    archiveArtifacts artifacts: 'app-coverage.xml', allowEmptyArchive: true
                    sh '''
                        export COMPOSE_PROJECT_NAME="movie-finder-backend-ci-${BUILD_NUMBER}"
                        make ci-down || true
                    '''
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
            agent any
            environment {
                ACR_SERVER = credentials('acr-login-server')
                ACR_CREDENTIALS = credentials('acr-credentials')
            }
            steps {
                script {
                    def tag = env.GIT_TAG_NAME ?: env.GIT_COMMIT.take(8)
                    env.BUILD_TAG  = tag
                    env.FULL_IMAGE = "${env.ACR_SERVER}/${env.SERVICE_NAME}:${tag}"
                }
                sh 'echo "$ACR_CREDENTIALS_PSW" | docker login "$ACR_SERVER" -u "$ACR_CREDENTIALS_USR" --password-stdin'
                sh "docker pull ${env.ACR_SERVER}/${env.SERVICE_NAME}:latest || true"
                sh """
                    docker build \
                        --cache-from ${env.ACR_SERVER}/${env.SERVICE_NAME}:latest \
                        -t ${env.FULL_IMAGE} \
                        .
                """
                sh "docker push ${env.FULL_IMAGE}"
                script {
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
                AZURE_SP        = credentials('azure-sp')
                AZURE_TENANT_ID = credentials('azure-tenant-id')
                AZURE_SUB_ID    = credentials('azure-sub-id')
                ACA_RG          = credentials('aca-staging-rg')
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
            when { buildingTag() }
            agent any
            environment {
                AZURE_SP        = credentials('azure-sp')
                AZURE_TENANT_ID = credentials('azure-tenant-id')
                AZURE_SUB_ID    = credentials('azure-sub-id')
                ACA_RG          = credentials('aca-prod-rg')
                ACA_NAME        = credentials('aca-prod-name')
                ACR_SERVER      = credentials('acr-login-server')
            }
            steps {
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
                    echo "Backend CI passed for ${env.BRANCH_NAME}."
                }
            }
        }
    }
}
