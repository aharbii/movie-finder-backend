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
//   GitHub, Docker, JUnit, Coverage, Credentials Binding, Git
// =============================================================================

pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
        disableConcurrentBuilds(abortPrevious: true)
        skipDefaultCheckout()
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
        COMPOSE_PROJECT_NAME = "movie-finder-backend-ci-${env.BUILD_NUMBER}"
    }

    stages {

        // ------------------------------------------------------------------ //
        stage('Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: scm.branches,
                    doGenerateSubmoduleConfigurations: false,
                    extensions: [[
                        $class: 'SubmoduleOption',
                        disableSubmodules: false,
                        parentCredentials: true,
                        recursiveSubmodules: true,
                        trackingSubmodules: false
                    ]],
                    userRemoteConfigs: scm.userRemoteConfigs
                ])
            }
        }

        // ------------------------------------------------------------------ //
        stage('Initialize') {
            steps {
                sh 'make init'
            }
        }

        // ------------------------------------------------------------------ //
        stage('Lint + Typecheck') {
            parallel {
                stage('Lint') {
                    steps { sh 'make lint' }
                }
                stage('Typecheck') {
                    steps { sh 'make typecheck' }
                }
            }
        }

        // ------------------------------------------------------------------ //
        stage('Test') {
            steps {
                sh 'make test-coverage'
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'junit.xml'
                    recordCoverage(
                        tools: [
                            [parser: 'COBERTURA', pattern: 'coverage.xml']
                        ],
                        id: 'coverage',
                        name: 'Chain Coverage',
                        sourceCodeRetention: 'EVERY_BUILD',
                        failOnError: false,
                        qualityGates: [
                            [threshold: 10.0, metric: 'LINE', baseline: 'PROJECT', unstable: true],
                            [threshold: 10.0, metric: 'BRANCH', baseline: 'PROJECT', unstable: true]
                        ]
                    )
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
                // Build from backend/ — that directory is the Docker build context.
                dir('backend') {
                    sh """
                        docker build \
                            --cache-from ${env.ACR_SERVER}/${env.SERVICE_NAME}:latest \
                            -t ${env.FULL_IMAGE} \
                            .
                    """
                }
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
                    // Remove locally-built images after push to prevent Jenkins node storage bloat.
                    // --rmi local in make ci-down skips images with a custom image: field, so we
                    // remove the built image explicitly here. Public base images (python:3.13-slim,
                    // postgres:16-alpine) are NOT removed — they stay cached on the Jenkins node.
                    sh "docker rmi ${env.FULL_IMAGE} || true"
                    script {
                        if (env.BRANCH_NAME == 'main') {
                            sh "docker rmi ${env.ACR_SERVER}/${env.SERVICE_NAME}:latest || true"
                        }
                    }
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
            sh 'make clean || true'
            sh 'make ci-down || true'
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
                    echo "Backend CI passed for ${env.BRANCH_NAME}."
                }
            }
        }
    }
}
