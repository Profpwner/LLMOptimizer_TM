#!/bin/bash

# Istio installation script
set -e

ISTIO_VERSION=${ISTIO_VERSION:-1.20.1}
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Installing Istio ${ISTIO_VERSION}..."

# Download Istio if not already present
if [ ! -d "${HOME}/istio-${ISTIO_VERSION}" ]; then
    echo "Downloading Istio ${ISTIO_VERSION}..."
    curl -L https://istio.io/downloadIstio | ISTIO_VERSION=${ISTIO_VERSION} sh -
    sudo mv istio-${ISTIO_VERSION}/bin/istioctl /usr/local/bin/
fi

# Pre-check
echo "Running Istio pre-installation checks..."
istioctl x precheck

# Create namespaces
echo "Creating namespaces..."
kubectl apply -f ${SCRIPT_DIR}/base/namespaces.yaml

# Install Istio using the operator
echo "Installing Istio control plane..."
istioctl install -f ${SCRIPT_DIR}/base/istio-operator.yaml --set values.pilot.env.PILOT_ENABLE_WORKLOAD_ENTRY_AUTOREGISTRATION=true -y

# Wait for Istio to be ready
echo "Waiting for Istio components to be ready..."
kubectl -n istio-system wait --for=condition=ready pod -l app=istiod --timeout=300s
kubectl -n istio-system wait --for=condition=ready pod -l app=istio-ingressgateway --timeout=300s

# Label default namespace for injection (optional)
kubectl label namespace default istio-injection=enabled --overwrite

# Verify installation
echo "Verifying Istio installation..."
istioctl verify-install -f ${SCRIPT_DIR}/base/istio-operator.yaml

# Install addons
echo "Installing Istio addons..."
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-${ISTIO_VERSION%.*}/samples/addons/prometheus.yaml
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-${ISTIO_VERSION%.*}/samples/addons/grafana.yaml
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-${ISTIO_VERSION%.*}/samples/addons/jaeger.yaml
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-${ISTIO_VERSION%.*}/samples/addons/kiali.yaml

echo "Istio installation completed successfully!"
echo ""
echo "To access Istio dashboards:"
echo "  Kiali: istioctl dashboard kiali"
echo "  Grafana: istioctl dashboard grafana"
echo "  Jaeger: istioctl dashboard jaeger"
echo "  Prometheus: istioctl dashboard prometheus"