// https://github.com/anssi-n/jenkins-pipeline-library.git
@Library('shared-library') _

pipeline {
    agent {
        kubernetes {
            yaml '''
apiVersion: v1
kind: Pod
metadata:
  name: huutoapp
  namespace: jenkins-agents
spec:   
  serviceAccountName: jenkins-agent
  nodeSelector:
    jenkins-agent: true
spec:
  containers:
  - name: kaniko
    image: registry.gitlab.com/gitlab-ci-utils/container-images/kaniko:debug
    command: ["cat"]
    tty: true
    workingDir: /home/jenkins/agent
    resources:
      requests:
        cpu: "500m"
        memory: "1Gi"
    volumeMounts:
    - name: docker-config
      mountPath: /kaniko/.docker
    - name: harbor-ca
      mountPath: /kaniko/ssl/certs/additional-ca-cert-bundle.crt
      subPath: additional-ca-cert-bundle.crt
  - name: cosign
    #image: cgr.dev/chainguard/cosign:latest-dev
    image: ghcr.io/sigstore/cosign/cosign:v3.0.5-dev
    command:
    - "cat"
    tty: true
    securityContext:
      runAsUser: 0
    volumeMounts:
    - name: docker-config
      mountPath: /docker-config
    - name: harbor-ca
      mountPath: /etc/ssl/certs/additional-ca-cert-bundle.crt
      subPath: additional-ca-cert-bundle.crt
  volumes:
  - name: docker-config
    secret:      
      secretName: harbor-credentials   
      items:
      - key: .dockerconfigjson
        path: config.json
  - name: harbor-ca
    secret:
      secretName: harbor-ca-cert   
      items:
      - key: ca.crt
        path: additional-ca-cert-bundle.crt
'''
        }
    }
    environment {
        REGISTRY = "harbor.anyman.homelab"
    }
    stages {
        stage('Determine target tag') {
            steps {
                container('jnlp') {
                    checkout scm
                    script {
                        def git_tag = sh(script: 'git describe --tags --exact-match 2>/dev/null || echo ""', returnStdout: true).trim()
                        if (git_tag && git_tag.startsWith("v")) {
                            env.IMAGE_TAG = git_tag.substring(1)
                            env.IS_RELEASE = "true"
                        } else {
                            env.IMAGE_TAG = "dev-${env.BUILD_NUMBER}"
                            env.IS_RELEASE = "false"
                        }
                    }
                }
            }
        }
        stage('Build and sign container images') {
            steps {
                script {
                    buildAndSignImage(
                        registry: env.REGISTRY,
                        imageName: "huutoapp/huutoapi",
                        dockerfile: "Dockerfile.huutoapi",
                        imageTag: env.IMAGE_TAG,
                        isRelease: env.IS_RELEASE
                    )

                    buildAndSignImage(
                        registry: env.REGISTRY,
                        imageName: "huutoapp/huutoworker",
                        dockerfile: "Dockerfile.huutoworker",
                        imageTag: env.IMAGE_TAG,
                        isRelease: env.IS_RELEASE
                    )
                }
            }
        }
    }
}