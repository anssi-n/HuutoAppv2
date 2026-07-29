pipeline {
    agent {
        label 'jenkins-jenkins-agent'
    }

    stages {
        stage('Build and Push Image') {
            steps {
                container('jnlp') {
                    checkout scm
                    sleep 180
                }
	        }
        }
    }
}