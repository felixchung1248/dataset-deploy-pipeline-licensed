pipeline {
    agent any

    parameters {
        string(name: 'DATASET_NAME', description: 'Dataset name')
        string(name: 'TICKET_ID', description: 'Ticket ID')
		string(name: 'DATASET_OWNER', description: 'Dataset owner')
        string(name: 'DATASET_DESCRIPTION', description: 'Dataset description')
    }

    environment {
        // DATAHUB_TOKEN = credentials('datahub-token')
        ZAMMAD_USR = credentials('zammad-usr')
        ZAMMAD_PW = credentials('zammad-pw')
		DENODO_DOCKER_IMAGE = "harbor.open.denodo.com/denodo-9/images/denodo-platform:latest"  
		PYTHON_DOCKER_IMAGE = "${env.DOCKER_REGISTRY}/${env.GOLDEN_PROJECT_NAME}/${env.GOLDEN_DOCKER_IMAGE}:${env.GOLDEN_DOCKER_TAG}"
		DNS_IP = sh(script: "kubectl get service -n kube-system kube-dns -o jsonpath='{.spec.clusterIP}'", returnStdout: true).trim()	
		creds = credentials('harbor-credentials')
    }

    stages {
        stage('Pre-flight Check') {
            steps {
                script {
                    if (!params.DATASET_NAME) {
                        error "The DATASET_NAME parameter is missing. Please provide the dataset name."
                    }
                    if (!params.TICKET_ID) {
                        error "The TICKET_ID parameter is missing. Please provide the ticket ID."
                    }
                    if (!params.DATASET_OWNER) {
                        error "The DATASET_OWNER parameter is missing. Please provide the dataset owner."
                    }
                    if (!params.DATASET_DESCRIPTION) {
                        error "The DATASET_DESCRIPTION parameter is missing. Please provide the dataset description."
                    }
                }
            }
        }

        stage('Run Dataset deploy') {
            steps {
                script {					
		    env.CONTAINER_NAME = "denodo_${env.BUILD_ID}"

                    // Run the container with necessary volumes and DNS settings, and execute the commands
                    sh """
						docker login --password=${env.creds_PSW} --user=${env.creds_USR}
                        docker run --name $CONTAINER_NAME -d -v /tmp:/tmp --dns=${DNS_IP} $DENODO_DOCKER_IMAGE tail -f /dev/null
                        docker exec $CONTAINER_NAME sh -c "mkdir -p /tmp/${CONTAINER_NAME}"
                        docker exec $CONTAINER_NAME sh -c "/opt/denodo/bin/export.sh --server //${env.DENODO_META_SANDBOX_URL}/admin --login admin --password admin --singleuser --repository-element admin:view:/${env.DATASET_NAME} --repository /tmp/${CONTAINER_NAME}"
                        docker exec $CONTAINER_NAME sh -c "/opt/denodo/bin/import.sh --server //${env.DENODO_META_PROD_URL}/admin?admin@admin --singleuser --repository /tmp/${CONTAINER_NAME} --element /databases/admin/views/${env.DATASET_NAME}.vql"
                        docker exec $CONTAINER_NAME sh -c "rm -rf /tmp/${CONTAINER_NAME}"
			docker stop $CONTAINER_NAME
                        docker rm $CONTAINER_NAME
                    """
		    
                }
            }
        }
		
	stage('Deploy data catalog dataset') {
            steps {
                script {					
                    sh """
                        python3 ${env.WORKSPACE}/data-catalog-deploy.py ticket_id=${env.TICKET_ID} zammad_usr=${env.ZAMMAD_USR} zammad_pw=${env.ZAMMAD_PW} zammad_url=${env.ZAMMAD_URL} dataset=${env.DATASET_NAME} datahub_url=${env.DATAHUB_URL} dataset_owner=${env.DATASET_OWNER} dataset_description="${env.DATASET_DESCRIPTION}"
                    """
                }
             }
        }
    }
}

   // post {
   //     always {
   //         // Optional: clean up
   //         // cleanWs()
   //     }
   // }

