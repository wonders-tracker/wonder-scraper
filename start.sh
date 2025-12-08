#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}=== Starting Wonder Scraper Full Stack ===${NC}"

# Function to kill process on port with retry
kill_port() {
    local port=$1
    local name=$2
    local max_attempts=3
    local attempt=1

    while lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; do
        if [ $attempt -gt $max_attempts ]; then
            echo -e "${RED}Failed to free port $port after $max_attempts attempts${NC}"
            return 1
        fi

        echo -e "${YELLOW}$name port $port in use. Killing (attempt $attempt)...${NC}"

        # Get all PIDs and kill them
        local pids=$(lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null)
        for pid in $pids; do
            if [ $attempt -lt $max_attempts ]; then
                kill $pid 2>/dev/null
            else
                kill -9 $pid 2>/dev/null  # Force kill on last attempt
            fi
        done

        sleep 1
        ((attempt++))
    done
    return 0
}

# Kill existing processes
kill_port 8000 "Backend" || exit 1
kill_port 3000 "Frontend" || exit 1

# Small delay to ensure ports are freed
sleep 1

# 1. Start Backend
echo -e "${GREEN}[1/3] Starting Backend API (FastAPI)...${NC}"
poetry run uvicorn app.main:app --reload --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GRAY}Backend PID: $BACKEND_PID${NC}"

# 2. Start Frontend
echo -e "${GREEN}[2/3] Starting Frontend (TanStack Start)...${NC}"
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "${GRAY}Frontend PID: $FRONTEND_PID${NC}"
cd ..

# 3. Wait for services
echo -e "${BLUE}Waiting for services to spin up...${NC}"
sleep 5

echo -e "${BOLD}${GREEN}[3/3] System Online!${NC}"
echo -e "  ${CYAN}Frontend:${NC} http://localhost:3000"
echo -e "  ${CYAN}Backend:${NC}  http://localhost:8000/api/v1"
echo -e "  ${CYAN}Swagger:${NC}  http://localhost:8000/api/v1/openapi.json"
echo ""
echo -e "${GRAY}Logs are being written to backend.log and frontend.log${NC}"
echo -e "${YELLOW}Press CTRL+C to stop all services.${NC}"
echo ""

# Trap CTRL+C to cleanup
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    kill_port 8000 "Backend" 2>/dev/null
    kill_port 3000 "Frontend" 2>/dev/null
    echo -e "${GREEN}Done.${NC}"
    exit 0
}
trap cleanup INT TERM

# Colorized log tailing function
colorize_logs() {
    while IFS= read -r line; do
        # Backend log coloring
        if [[ $line == *"==> backend.log"* ]]; then
            echo -e "${BOLD}${BLUE}$line${NC}"
        elif [[ $line == *"==> frontend.log"* ]]; then
            echo -e "${BOLD}${CYAN}$line${NC}"
        # Error highlighting
        elif [[ $line == *"ERROR"* ]] || [[ $line == *"Error"* ]] || [[ $line == *"error"* ]]; then
            echo -e "${RED}$line${NC}"
        # Warning highlighting
        elif [[ $line == *"WARNING"* ]] || [[ $line == *"Warning"* ]] || [[ $line == *"warn"* ]]; then
            echo -e "${YELLOW}$line${NC}"
        # Info highlighting
        elif [[ $line == *"INFO"* ]]; then
            echo -e "${GREEN}$line${NC}"
        # HTTP methods
        elif [[ $line == *"GET"* ]] || [[ $line == *"POST"* ]] || [[ $line == *"PUT"* ]] || [[ $line == *"DELETE"* ]]; then
            echo -e "${CYAN}$line${NC}"
        # Success messages
        elif [[ $line == *"200"* ]] || [[ $line == *"success"* ]] || [[ $line == *"ready"* ]]; then
            echo -e "${GREEN}$line${NC}"
        # Default
        else
            echo -e "${GRAY}$line${NC}"
        fi
    done
}

# Tail logs with colors
tail -f backend.log frontend.log 2>/dev/null | colorize_logs
