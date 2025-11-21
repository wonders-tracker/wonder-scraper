#!/bin/bash

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting Wonder Scraper Full Stack ===${NC}"

# check if running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "Backend port 8000 already in use. Killing..."
    kill $(lsof -Pi :8000 -sTCP:LISTEN -t)
fi

if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null ; then
    echo "Frontend port 3000 already in use. Killing..."
    kill $(lsof -Pi :3000 -sTCP:LISTEN -t)
fi

# 1. Start Backend
echo -e "${GREEN}[1/3] Starting Backend API (FastAPI)...${NC}"
poetry run uvicorn app.main:app --reload --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# 2. Start Frontend
echo -e "${GREEN}[2/3] Starting Frontend (TanStack Start)...${NC}"
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
cd ..

# 3. Wait for services
echo -e "${BLUE}Waiting for services to spin up...${NC}"
sleep 5

echo -e "${GREEN}[3/3] System Online!${NC}"
echo -e "Frontend: http://localhost:3000"
echo -e "Backend:  http://localhost:8000/api/v1"
echo -e "Swagger:  http://localhost:8000/api/v1/openapi.json"
echo -e "${BLUE}Logs are being written to backend.log and frontend.log${NC}"
echo -e "Press CTRL+C to stop all services."

# Trap CTRL+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT

# Tail logs
tail -f backend.log frontend.log

