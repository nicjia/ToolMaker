#!/bin/bash
# TOOLMAKER Testing Workflow & Command Summary
# May 20, 2026

# ==============================================================================
# STEP 1: Repository Structure Setup
# ==============================================================================

# Goal: Convert individual task.yaml files into task directories (required by TOOLMAKER)
cd /Users/nick/ToolMaker

# Create task directories for each financial repository
mkdir -p task_yfinance task_backtrader task_riskportfolio task_medical_baseline

# Move YAML files into their respective directories
mv task-yfinance.yaml task_yfinance/task.yaml
mv task-backtrader.yaml task_backtrader/task.yaml
mv task-riskportfolio.yaml task_riskportfolio/task.yaml

# WHY: TOOLMAKER expects a folder containing:
#   - task.yaml
#   - (optional) data/ folder with test files
#   - (optional) README explaining the task

# ==============================================================================
# STEP 2: Task Schema Validation
# ==============================================================================

# TOOLMAKER uses ToolArena's ToolDefinition class, which requires:
#   - name: unique tool identifier
#   - repo: {name, url} (Git repository)
#   - papers: list of paper references
#   - category: task domain
#   - arguments: list of {name, type, description}
#   - returns: list of {name, type, description}
#   - example: sample invocation with concrete values (REQUIRED for LLM context)

# ITERATION NOTES:
# First attempt failed: arguments/returns were dicts, not lists → schema error
# Second attempt failed: missing 'example' field → AttributeError in ToolDefinition
# Third attempt (CURRENT): Added example section with proper argument values

# ==============================================================================
# STEP 3: TOOLMAKER Two-Phase Pipeline
# ==============================================================================

# PHASE 1: Install (Create Docker environment)
# Purpose: Set up isolated container with repo dependencies installed
uv run python -m toolmaker install task_yfinance --name yfinance_tool --force

# Commands executed in sequence:
#   uv run python -m toolmaker install task_yfinance --name yfinance_tool --force
#   uv run python -m toolmaker install task_backtrader --name backtrader_tool --force
#   uv run python -m toolmaker install task_riskportfolio --name riskportfolio_tool --force

# What happens:
# 1. TOOLMAKER reads task.yaml
# 2. Clones the repository specified in repo.url
# 3. Creates a Dockerfile with dependency installation steps
# 4. Generates install.sh script
# 5. Builds Docker image (requires base image: ghcr.io/katherlab/toolmaker:cpu)

# ERROR ENCOUNTERED HERE:
#   ImageNotFound: 404 Client Error ... ghcr.io/katherlab/toolmaker:cpu
# 
# ROOT CAUSE: Docker image not pulled locally
# FIX: Must pull images before running install
#   docker pull ghcr.io/katherlab/toolmaker:cpu
#   docker pull ghcr.io/katherlab/toolmaker:cuda  # if GPU available

# ==============================================================================
# PHASE 2: Create (Use LLM to generate code)
# Purpose: Use Claude/Gemini to generate tool implementation
# This step runs AFTER install completes successfully

uv run python -m toolmaker create task_yfinance --name yfinance_tool --installed yfinance_tool

# What happens:
# 1. Loads the installed environment (created in Phase 1)
# 2. Sends task description + repository structure to LLM (Gemini in our case)
# 3. LLM generates Python implementation
# 4. Executes generated code in Docker container to validate
# 5. If validation fails, enters self-correction loop:
#    - Parse error message
#    - Send error back to LLM with context
#    - Regenerate code (up to max_steps=30 iterations)

# ==============================================================================
# STEP 4: API Configuration (LiteLLM + Gemini)
# ==============================================================================

# TOOLMAKER uses LiteLLM library to abstract LLM provider differences
# Configuration in toolmaker/llm/__init__.py:

LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini/gemini-pro")
LLM_MODEL_REASONING: str = os.getenv("LLM_MODEL_REASONING", "gemini/gemini-2.5-pro")
LLM_MODEL_SUMMARY: str = os.getenv("LLM_MODEL_SUMMARY", "gemini/gemini-pro")

# Our .env configuration:
# CUDA_VISIBLE_DEVICES = 0  # if GPU available

# Rate limiting is handled by tenacity:
#   - litellm_completion_retry_on_rate_limit: retry on RateLimitError
#   - litellm_completion_retry_on_api_error: retry on APIError
#   - MAX_COST: $5.0 limit per session (hardcoded)

# ==============================================================================
# STEP 5: Expected Outputs
# ==============================================================================

# Upon successful completion, tool_output/ structure:
#
# tool_output/
#   ├── install/
#   │   ├── yfinance_tool/
#   │   │   └── install.sh
#   │   ├── backtrader_tool/
#   │   │   └── install.sh
#   │   └── riskportfolio_tool/
#   │       └── install.sh
#   │
#   └── tools/
#       ├── yfinance_tool/
#       │   ├── code.py           # Generated implementation
#       │   ├── task.yaml         # Copy of task definition
#       │   ├── tool_runner.py    # Execution wrapper
#       │   └── logs.jsonl        # Detailed execution trace
#       ├── backtrader_tool/
#       │   ├── code.py
#       │   ├── task.yaml
#       │   ├── tool_runner.py
#       │   └── logs.jsonl
#       └── riskportfolio_tool/
#           ├── code.py
#           ├── task.yaml
#           ├── tool_runner.py
#           └── logs.jsonl

# ==============================================================================
# STEP 6: Visualization & Analysis
# ==============================================================================

# TOOLMAKER generates logs.jsonl with full execution trace (LLM calls, errors, corrections)
# Can visualize with:

uv run python -m toolmaker.utils.visualize \
  -i tool_output/tools/yfinance_tool/logs.jsonl \
  -o yfinance_tool_trajectory.html

# This creates an interactive HTML showing:
# - Agent state at each step
# - LLM prompts and responses
# - Error messages and fixes applied
# - Final code

# ==============================================================================
# SUMMARY: What We've Done
# ==============================================================================

# ✅ COMPLETE:
#   1. Selected 3 financial repositories (yfinance, backtrader, Riskfolio-Lib)
#   2. Created task.yaml files with correct ToolArena schema
#   3. Validated task definitions against Pydantic model
#   4. Configured Gemini API key via LiteLLM
#   5. Understood the two-phase TOOLMAKER pipeline

# 🔄 BLOCKED (Docker issue):
#   1. Docker image pull required before Phase 1 (install) can run
#   2. Need: docker pull ghcr.io/katherlab/toolmaker:cpu

# 📋 TODO:
#   1. Pull Docker images
#   2. Re-run install phase for all 3 tasks
#   3. Once install succeeds, run create phase
#   4. Collect logs and success/failure data
#   5. Analyze failure modes specific to financial domain
#   6. Complete final report

# ==============================================================================
# How to Resume Tomorrow (if Docker blocker remains)
# ==============================================================================

# Option A: Pull Docker images and retry
docker pull ghcr.io/katherlab/toolmaker:cpu
docker pull ghcr.io/katherlab/toolmaker:cuda

# Then resume:
cd /Users/nick/ToolMaker
for task in task_yfinance task_backtrader task_riskportfolio; do
  name=${task#task_}
  uv run python -m toolmaker install $task --name "${name}_tool" --force
  uv run python -m toolmaker create $task --name "${name}_tool" --installed "${name}_tool" --force
done

# Option B: If free-tier API runs out of quota
# Use local Ollama or Claude via separate API keys (modify LLM_MODEL env vars)

# ==============================================================================
