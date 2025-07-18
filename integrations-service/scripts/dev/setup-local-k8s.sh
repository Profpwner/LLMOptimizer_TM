#!/bin/bash

# setup-local-k8s.sh - Configure local Kubernetes for LLMOptimizer development
# Supports Minikube and Kind

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="llmoptimizer-dev"
MINIKUBE_MEMORY="4096"
MINIKUBE_CPUS="4"
MINIKUBE_DISK_SIZE="20g"
REGISTRY_NAME="llmoptimizer-registry"
REGISTRY_PORT="5000"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_tools=()
    
    for tool in docker kubectl; do
        if ! command -v $tool &> /dev/null; then
            missing_tools+=($tool)
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Please run './install-dev-tools.sh' first"
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker Desktop."
        exit 1
    fi
    
    log_success "All prerequisites met"
}

setup_minikube() {
    log_info "Setting up Minikube cluster..."
    
    # Check if Minikube is installed
    if ! command -v minikube &> /dev/null; then
        log_error "Minikube is not installed. Please run './install-dev-tools.sh' first"
        return 1
    fi
    
    # Delete existing cluster if it exists
    if minikube status -p $CLUSTER_NAME &> /dev/null; then
        log_warning "Existing Minikube cluster found. Deleting..."
        minikube delete -p $CLUSTER_NAME
    fi
    
    # Start Minikube with proper resources
    log_info "Starting Minikube cluster..."
    minikube start \
        -p $CLUSTER_NAME \
        --memory=$MINIKUBE_MEMORY \
        --cpus=$MINIKUBE_CPUS \
        --disk-size=$MINIKUBE_DISK_SIZE \
        --kubernetes-version=v1.28.3 \
        --driver=docker \
        --addons=metrics-server,dashboard,ingress,registry
    
    # Set kubectl context
    kubectl config use-context $CLUSTER_NAME
    
    # Enable additional addons
    log_info "Enabling Minikube addons..."
    minikube addons enable ingress -p $CLUSTER_NAME
    minikube addons enable ingress-dns -p $CLUSTER_NAME
    minikube addons enable metrics-server -p $CLUSTER_NAME
    minikube addons enable dashboard -p $CLUSTER_NAME
    minikube addons enable registry -p $CLUSTER_NAME
    
    # Wait for cluster to be ready
    log_info "Waiting for cluster to be ready..."
    kubectl wait --for=condition=Ready nodes --all --timeout=300s
    
    log_success "Minikube cluster setup complete"
}

setup_kind() {
    log_info "Setting up Kind cluster..."
    
    # Check if Kind is installed
    if ! command -v kind &> /dev/null; then
        log_error "Kind is not installed. Please run './install-dev-tools.sh' first"
        return 1
    fi
    
    # Delete existing cluster if it exists
    if kind get clusters | grep -q $CLUSTER_NAME; then
        log_warning "Existing Kind cluster found. Deleting..."
        kind delete cluster --name $CLUSTER_NAME
    fi
    
    # Create Kind configuration
    cat > /tmp/kind-config.yaml <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: $CLUSTER_NAME
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
      - containerPort: 30000
        hostPort: 30000
        protocol: TCP
      - containerPort: 30001
        hostPort: 30001
        protocol: TCP
  - role: worker
  - role: worker
containerdConfigPatches:
  - |-
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:${REGISTRY_PORT}"]
      endpoint = ["http://${REGISTRY_NAME}:5000"]
EOF
    
    # Create cluster
    log_info "Creating Kind cluster..."
    kind create cluster --config /tmp/kind-config.yaml
    
    # Set kubectl context
    kubectl config use-context kind-$CLUSTER_NAME
    
    # Install NGINX Ingress Controller for Kind
    log_info "Installing NGINX Ingress Controller..."
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
    
    # Wait for ingress to be ready
    kubectl wait --namespace ingress-nginx \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller \
        --timeout=300s
    
    log_success "Kind cluster setup complete"
}

setup_local_registry() {
    log_info "Setting up local Docker registry..."
    
    # Check if registry already exists
    if docker ps -a | grep -q $REGISTRY_NAME; then
        log_warning "Registry already exists. Removing..."
        docker rm -f $REGISTRY_NAME
    fi
    
    # Run local registry
    docker run -d \
        --restart=always \
        --name $REGISTRY_NAME \
        -p ${REGISTRY_PORT}:5000 \
        registry:2
    
    # For Kind: Connect registry to cluster network
    if [[ "$K8S_PROVIDER" == "kind" ]]; then
        docker network connect "kind" $REGISTRY_NAME || true
        
        # Document the local registry
        cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF
    fi
    
    # For Minikube: Enable registry addon is already done
    
    log_success "Local registry setup complete at localhost:${REGISTRY_PORT}"
}

install_metrics_server() {
    log_info "Installing metrics server..."
    
    # Check if metrics-server is already installed
    if kubectl get deployment -n kube-system metrics-server &> /dev/null; then
        log_warning "Metrics server already installed"
        return
    fi
    
    # Install metrics server (for Kind)
    if [[ "$K8S_PROVIDER" == "kind" ]]; then
        kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
        
        # Patch metrics server for local development
        kubectl patch deployment metrics-server -n kube-system --type='json' \
            -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
    fi
    
    log_success "Metrics server installed"
}

create_namespaces() {
    log_info "Creating Kubernetes namespaces..."
    
    kubectl create namespace llmoptimizer-dev --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace llmoptimizer-staging --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
    
    # Set default namespace
    kubectl config set-context --current --namespace=llmoptimizer-dev
    
    log_success "Namespaces created"
}

setup_ingress_hosts() {
    log_info "Setting up local hosts entries..."
    
    # Define local domains
    local domains=(
        "api.llmoptimizer.local"
        "auth.llmoptimizer.local"
        "billing.llmoptimizer.local"
        "notifications.llmoptimizer.local"
        "analytics.llmoptimizer.local"
        "monitoring.llmoptimizer.local"
        "registry.llmoptimizer.local"
    )
    
    # Get cluster IP
    local cluster_ip="127.0.0.1"
    if [[ "$K8S_PROVIDER" == "minikube" ]]; then
        cluster_ip=$(minikube ip -p $CLUSTER_NAME)
    fi
    
    log_info "Adding hosts entries (may require sudo password)..."
    for domain in "${domains[@]}"; do
        if ! grep -q "$domain" /etc/hosts; then
            echo "$cluster_ip $domain" | sudo tee -a /etc/hosts > /dev/null
            log_success "Added $domain -> $cluster_ip"
        else
            log_warning "$domain already in /etc/hosts"
        fi
    done
}

create_dev_secrets() {
    log_info "Creating development secrets..."
    
    # Create basic auth secret for development
    kubectl create secret generic dev-basic-auth \
        --from-literal=username=admin \
        --from-literal=password=admin123 \
        --namespace=llmoptimizer-dev \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Create JWT secret
    kubectl create secret generic jwt-secret \
        --from-literal=secret-key=dev-secret-key-change-in-production \
        --namespace=llmoptimizer-dev \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Create database secrets
    kubectl create secret generic postgres-secret \
        --from-literal=username=postgres \
        --from-literal=password=postgres123 \
        --namespace=llmoptimizer-dev \
        --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl create secret generic redis-secret \
        --from-literal=password=redis123 \
        --namespace=llmoptimizer-dev \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log_success "Development secrets created"
}

print_cluster_info() {
    echo
    echo "========================================="
    echo "Kubernetes Cluster Setup Complete!"
    echo "========================================="
    echo
    echo "Cluster: $CLUSTER_NAME"
    echo "Provider: $K8S_PROVIDER"
    echo "Context: $(kubectl config current-context)"
    echo "Namespace: llmoptimizer-dev"
    echo
    echo "Local Registry: localhost:${REGISTRY_PORT}"
    echo
    echo "Local domains configured:"
    echo "  - api.llmoptimizer.local"
    echo "  - auth.llmoptimizer.local"
    echo "  - billing.llmoptimizer.local"
    echo "  - notifications.llmoptimizer.local"
    echo "  - analytics.llmoptimizer.local"
    echo "  - monitoring.llmoptimizer.local"
    echo
    if [[ "$K8S_PROVIDER" == "minikube" ]]; then
        echo "Minikube IP: $(minikube ip -p $CLUSTER_NAME)"
        echo
        echo "Access Kubernetes Dashboard:"
        echo "  minikube dashboard -p $CLUSTER_NAME"
    else
        echo "Access cluster:"
        echo "  kubectl cluster-info"
    fi
    echo
    echo "Next steps:"
    echo "  1. Run './init-dev-env.sh' to initialize the development environment"
    echo "  2. Use 'kubectl get pods -A' to view all pods"
    echo "  3. Use 'k9s' for interactive cluster management"
    echo "========================================="
}

# Main execution
main() {
    log_info "Starting local Kubernetes setup..."
    
    # Check prerequisites
    check_prerequisites
    
    # Parse arguments
    K8S_PROVIDER="${1:-minikube}"
    
    if [[ "$K8S_PROVIDER" != "minikube" && "$K8S_PROVIDER" != "kind" ]]; then
        log_error "Invalid provider: $K8S_PROVIDER. Use 'minikube' or 'kind'"
        exit 1
    fi
    
    log_info "Using Kubernetes provider: $K8S_PROVIDER"
    
    # Setup cluster based on provider
    if [[ "$K8S_PROVIDER" == "minikube" ]]; then
        setup_minikube
    else
        setup_kind
    fi
    
    # Common setup
    setup_local_registry
    install_metrics_server
    create_namespaces
    setup_ingress_hosts
    create_dev_secrets
    
    # Print summary
    print_cluster_info
}

# Show usage if --help is passed
if [[ "${1:-}" == "--help" ]]; then
    echo "Usage: $0 [provider]"
    echo "  provider: 'minikube' (default) or 'kind'"
    echo
    echo "Examples:"
    echo "  $0              # Use Minikube"
    echo "  $0 minikube     # Use Minikube"
    echo "  $0 kind         # Use Kind"
    exit 0
fi

# Run main function
main "$@"