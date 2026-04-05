// =============================================================================
// movie-finder-backend — Jenkins declarative pipeline
//
// Stages:
//   1. Checkout (recursive submodules)
//   2. Initialize
//   3. Lint + Typecheck — parallel
//   4. Test — backend app (PostgreSQL via docker-compose) with coverage
//   5. Build App Image — push to ACR (main branch and tags only)
//
// Deploy stages have been removed from this pipeline.
// Staging and production deployments are orchestrated by the root
// aharbii/movie-finder Jenkinsfile, which pulls the built image from ACR
// after this pipeline completes.
//
// Triggers (configure in Jenkins job or via GitHub Branch Source plugin):
//   • Every PR to main
//   • Every push to main
//   • Every git tag matching v*
//
// Jenkins credentials required (Manage Jenkins → Credentials → Global):
//
//   acr-login-server   Secret Text      Full ACR hostname, e.g. myacr.azurecr.io
//   acr-credentials    Username+Pass    SP App ID (user) + client secret (pass)
//                                       Used for "docker login" to ACR
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
                        name: 'Backend Coverage',
                        sourceCodeRetention: 'EVERY_BUILD',
                        sourceDirectories: [[path: 'app/src']],
                        failOnError: false,
                        qualityGates: [
                            [threshold: 10.0, metric: 'LINE', baseline: 'PROJECT'],
                            [threshold: 10.0, metric: 'BRANCH', baseline: 'PROJECT']
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
                // The workspace root IS the backend repo root — build context is '.'.
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
                    echo "Release ${env.GIT_TAG_NAME} (${env.BUILD_TAG}) image pushed to ACR. Deploy via aharbii/movie-finder pipeline."
                } else if (env.BRANCH_NAME == 'main') {
                    echo "Build ${env.BUILD_TAG} image pushed to ACR. Deploy via aharbii/movie-finder pipeline."
                } else {
                    echo "Backend CI passed for ${env.BRANCH_NAME}."
                }
            }
        }
    }
}
