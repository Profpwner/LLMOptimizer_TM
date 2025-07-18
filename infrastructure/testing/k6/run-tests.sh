#!/bin/bash

# K6 Load Testing Script for LLMOptimizer
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test environment
TEST_ENV=${TEST_ENV:-staging}
BASE_URL=${BASE_URL:-https://staging-api.llmoptimizer.com}
WS_URL=${WS_URL:-wss://staging-api.llmoptimizer.com/ws}

# K6 installation check
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}k6 is not installed. Installing...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install k6
    else
        sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
        echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
        sudo apt-get update
        sudo apt-get install k6
    fi
fi

# Function to run test
run_test() {
    local TEST_TYPE=$1
    local SCENARIO=$2
    
    echo -e "\n${YELLOW}Running $TEST_TYPE test...${NC}"
    
    k6 run \
        --env BASE_URL=$BASE_URL \
        --env WS_URL=$WS_URL \
        --env SCENARIO=$SCENARIO \
        --out influxdb=http://localhost:8086/k6 \
        --summary-export=results/${TEST_TYPE}-summary.json \
        $3
}

# Create results directory
mkdir -p results

# Menu for test selection
echo -e "${GREEN}LLMOptimizer Load Testing Suite${NC}"
echo "================================"
echo "Environment: $TEST_ENV"
echo "API URL: $BASE_URL"
echo ""
echo "Select test type:"
echo "1) Smoke Test (2 users, 1 minute)"
echo "2) Load Test (ramp to 1000 users)"
echo "3) Stress Test (incremental load)"
echo "4) Spike Test (sudden traffic)"
echo "5) Soak Test (500 users, 2 hours)"
echo "6) WebSocket Test"
echo "7) Full Test Suite"
echo "8) Custom Test"
echo ""

read -p "Enter your choice (1-8): " choice

case $choice in
    1)
        run_test "smoke" "smoke" "load-test-config.js"
        ;;
    2)
        run_test "load" "load" "load-test-config.js"
        ;;
    3)
        run_test "stress" "stress" "load-test-config.js"
        ;;
    4)
        run_test "spike" "spike" "load-test-config.js"
        ;;
    5)
        echo -e "${YELLOW}Warning: Soak test runs for 2 hours${NC}"
        read -p "Continue? (y/n): " confirm
        if [[ $confirm == "y" ]]; then
            run_test "soak" "soak" "load-test-config.js"
        fi
        ;;
    6)
        run_test "websocket" "default" "websocket-test.js"
        ;;
    7)
        echo -e "${YELLOW}Running full test suite...${NC}"
        run_test "smoke" "smoke" "load-test-config.js"
        run_test "load" "load" "load-test-config.js"
        run_test "websocket" "default" "websocket-test.js"
        ;;
    8)
        read -p "Enter number of VUs: " vus
        read -p "Enter duration (e.g., 30s, 5m): " duration
        echo -e "${YELLOW}Running custom test with $vus VUs for $duration${NC}"
        k6 run --vus $vus --duration $duration \
            --env BASE_URL=$BASE_URL \
            --summary-export=results/custom-summary.json \
            load-test-config.js
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Generate HTML report
if command -v k6-reporter &> /dev/null; then
    echo -e "\n${GREEN}Generating HTML report...${NC}"
    k6-reporter --summary-file results/*.json --output results/report.html
fi

echo -e "\n${GREEN}Test completed! Results saved in ./results/${NC}"