#!/bin/bash

# install-dev-tools.sh - Install required development tools for LLMOptimizer
# Supports macOS and Linux

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

check_command() {
    if command -v "$1" &> /dev/null; then
        log_success "$1 is already installed"
        return 0
    else
        return 1
    fi
}

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        log_error "Unsupported OS: $OSTYPE"
        exit 1
    fi
}

detect_arch() {
    local arch=$(uname -m)
    case $arch in
        x86_64)
            echo "amd64"
            ;;
        arm64|aarch64)
            echo "arm64"
            ;;
        *)
            log_error "Unsupported architecture: $arch"
            exit 1
            ;;
    esac
}

install_homebrew() {
    if [[ "$OS" == "macos" ]]; then
        if ! check_command brew; then
            log_info "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            
            # Add Homebrew to PATH for Apple Silicon Macs
            if [[ -f "/opt/homebrew/bin/brew" ]]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            fi
            log_success "Homebrew installed"
        fi
    fi
}

install_docker() {
    if ! check_command docker; then
        log_info "Installing Docker..."
        if [[ "$OS" == "macos" ]]; then
            brew install --cask docker
            log_warning "Please start Docker Desktop manually"
        else
            # Linux installation
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER
            rm get-docker.sh
            log_warning "Please log out and back in for Docker group changes to take effect"
        fi
        log_success "Docker installed"
    fi
}

install_kubectl() {
    if ! check_command kubectl; then
        log_info "Installing kubectl..."
        if [[ "$OS" == "macos" ]]; then
            brew install kubectl
        else
            # Linux installation
            curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/${ARCH}/kubectl"
            sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
            rm kubectl
        fi
        log_success "kubectl installed"
    fi
}

install_minikube() {
    if ! check_command minikube; then
        log_info "Installing Minikube..."
        if [[ "$OS" == "macos" ]]; then
            brew install minikube
        else
            # Linux installation
            curl -LO "https://storage.googleapis.com/minikube/releases/latest/minikube-linux-${ARCH}"
            sudo install minikube-linux-${ARCH} /usr/local/bin/minikube
            rm minikube-linux-${ARCH}
        fi
        log_success "Minikube installed"
    fi
}

install_kind() {
    if ! check_command kind; then
        log_info "Installing kind..."
        if [[ "$OS" == "macos" ]]; then
            brew install kind
        else
            # Linux installation
            curl -Lo ./kind "https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-${ARCH}"
            chmod +x ./kind
            sudo mv ./kind /usr/local/bin/kind
        fi
        log_success "kind installed"
    fi
}

install_helm() {
    if ! check_command helm; then
        log_info "Installing Helm..."
        if [[ "$OS" == "macos" ]]; then
            brew install helm
        else
            # Linux installation
            curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
        fi
        log_success "Helm installed"
    fi
}

install_skaffold() {
    if ! check_command skaffold; then
        log_info "Installing Skaffold..."
        if [[ "$OS" == "macos" ]]; then
            brew install skaffold
        else
            # Linux installation
            curl -Lo skaffold "https://storage.googleapis.com/skaffold/releases/latest/skaffold-linux-${ARCH}"
            sudo install skaffold /usr/local/bin/
            rm skaffold
        fi
        log_success "Skaffold installed"
    fi
}

install_k9s() {
    if ! check_command k9s; then
        log_info "Installing k9s..."
        if [[ "$OS" == "macos" ]]; then
            brew install k9s
        else
            # Linux installation
            curl -sS https://webinstall.dev/k9s | bash
        fi
        log_success "k9s installed"
    fi
}

install_stern() {
    if ! check_command stern; then
        log_info "Installing stern..."
        if [[ "$OS" == "macos" ]]; then
            brew install stern
        else
            # Linux installation
            curl -Lo stern "https://github.com/stern/stern/releases/download/v1.26.0/stern_1.26.0_linux_${ARCH}.tar.gz"
            tar -xzf stern
            sudo mv stern /usr/local/bin/
            rm stern
        fi
        log_success "stern installed"
    fi
}

install_python_tools() {
    log_info "Installing Python development tools..."
    
    # Check for Python 3
    if ! check_command python3; then
        if [[ "$OS" == "macos" ]]; then
            brew install python@3.11
        else
            sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
        fi
    fi
    
    # Install Python dev tools
    pip3 install --user --upgrade pip setuptools wheel
    pip3 install --user --upgrade black flake8 mypy pytest pytest-cov pytest-asyncio
    pip3 install --user --upgrade httpie jq yq
    
    log_success "Python development tools installed"
}

install_go_tools() {
    log_info "Installing Go development tools..."
    
    # Check for Go
    if ! check_command go; then
        if [[ "$OS" == "macos" ]]; then
            brew install go
        else
            # Install latest Go
            GO_VERSION="1.21.5"
            wget "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz"
            sudo rm -rf /usr/local/go
            sudo tar -C /usr/local -xzf "go${GO_VERSION}.linux-${ARCH}.tar.gz"
            rm "go${GO_VERSION}.linux-${ARCH}.tar.gz"
            echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
        fi
    fi
    
    # Install Go dev tools
    go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
    go install golang.org/x/tools/cmd/goimports@latest
    go install github.com/go-delve/delve/cmd/dlv@latest
    
    log_success "Go development tools installed"
}

install_database_tools() {
    log_info "Installing database tools..."
    
    if [[ "$OS" == "macos" ]]; then
        brew install postgresql redis mongodb-community
    else
        # Install PostgreSQL client
        sudo apt-get update && sudo apt-get install -y postgresql-client
        
        # Install Redis client
        sudo apt-get install -y redis-tools
        
        # Install MongoDB client
        wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
        echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
        sudo apt-get update && sudo apt-get install -y mongodb-mongosh
    fi
    
    log_success "Database tools installed"
}

install_additional_tools() {
    log_info "Installing additional development tools..."
    
    if [[ "$OS" == "macos" ]]; then
        brew install jq yq git-flow watch tmux htop ctop lazydocker
    else
        sudo apt-get update && sudo apt-get install -y jq git-flow watch tmux htop
        
        # Install yq
        sudo wget -qO /usr/local/bin/yq "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_${ARCH}"
        sudo chmod +x /usr/local/bin/yq
        
        # Install ctop
        sudo wget https://github.com/bcicen/ctop/releases/download/v0.7.7/ctop-0.7.7-linux-${ARCH} -O /usr/local/bin/ctop
        sudo chmod +x /usr/local/bin/ctop
        
        # Install lazydocker
        curl https://raw.githubusercontent.com/jesseduffield/lazydocker/master/scripts/install_update_linux.sh | bash
    fi
    
    log_success "Additional tools installed"
}

# Main execution
main() {
    log_info "Starting development tools installation..."
    
    # Detect OS and architecture
    OS=$(detect_os)
    ARCH=$(detect_arch)
    
    log_info "Detected OS: $OS, Architecture: $ARCH"
    
    # Install tools
    if [[ "$OS" == "macos" ]]; then
        install_homebrew
    fi
    
    install_docker
    install_kubectl
    install_minikube
    install_kind
    install_helm
    install_skaffold
    install_k9s
    install_stern
    install_python_tools
    install_go_tools
    install_database_tools
    install_additional_tools
    
    log_success "All development tools installed successfully!"
    log_info "Next steps:"
    echo "  1. Start Docker Desktop (if on macOS)"
    echo "  2. Run './setup-local-k8s.sh' to set up local Kubernetes"
    echo "  3. Run './init-dev-env.sh' to initialize the development environment"
}

# Run main function
main "$@"