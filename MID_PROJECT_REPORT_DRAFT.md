# Quant-Bench: Evaluating TOOLMAKER's Generalization to Financial Software

**Nicholas Jiang, Amal Padhye, Connor Wang**

---

## 1. Introduction

Recent work in autonomous software engineering has demonstrated the potential for LLM-based agents to generate functional code from task descriptions. TOOLMAKER (Wölflein et al., 2025) achieves an 80% success rate on diverse scientific tasks spanning medical imaging and computational biology. However, the generalization of ToolMaker to specialized domains outside its original benchmark remains unexplored. This project investigates whether TOOLMAKER can successfully generate tools for problems in quantitative finance—a domain characterized by complex mathematical transformations, real-time data handling, and strict correctness requirements.

Our follow-up project, **Quant-Bench**, establishes a benchmark of three financial software engineering tasks derived from popular, well-maintained repositories in portfolio optimization, backtesting, and financial data retrieval. We aim to:  
1. Measure TOOLMAKER's success rate on financial domain tasks  
2. Identify domain-specific challenges in financial software generation  
3. Compare failure modes against the original medical/scientific benchmark

---

## 2. Methodology

### 2.1 Task Selection and Experimental Design

We curated three financial software repositories representing different sub-domains:

| Repository | Task | Input | Output |
|---|---|---|---|
| **yfinance** | Fetch historical stock prices | ticker, date range | daily closing prices (dict) |
| **backtrader** | Backtest Moving Average strategy | CSV OHLCV data, MA periods | portfolio final value (float) |
| **Riskfolio-Lib** | Optimize portfolio Sharpe ratio | returns CSV, target risk | asset weight allocations (dict) |

### 2.2 TOOLMAKER Pipeline Configuration

For each task, we:

1. **Defined the task** in `task.yaml` format (ToolArena schema) with:
   - Repository URL and basic metadata (name, category, papers)
   - Input/output argument specifications with types and descriptions
   - An example invocation demonstrating expected behavior

2. **Configured the LLM backend** via LiteLLM proxy to Gemini API:
   ```
   LLM_MODEL="gemini/gemini-pro"
   LLM_MODEL_REASONING="gemini/gemini-2.5-pro"
   ```

3. **Prepared Docker execution environment:**
   - TOOLMAKER uses containerized environments to isolate and test generated code
   - Used official TOOLMAKER Docker images (`ghcr.io/katherlab/toolmaker:cpu`)

### 2.3 Benchmark Definition

The **Quant-Bench** evaluation criteria:
- **Success**: Generated code runs without error and returns correct types
- **Robustness**: Code handles edge cases (empty data, invalid parameters)
- **Latency**: Tool creation time under 10 minutes (API quota budget)

---

## 3. Progress & Preliminary Results

### 3.1 Environment Setup Status

✅ **Completed:**
- Task definition files created for all 3 repositories with correct ToolArena schema
- Gemini free-tier API key configured in `.env` file
- LiteLLM library integrated for Gemini API access
- Repository URLs verified and accessible

### 3.2 Execution Attempt & Challenges Encountered

We executed TOOLMAKER's two-phase pipeline:
```bash
# Phase 1: Environment installation (sets up Docker container)
uv run python -m toolmaker install task_yfinance --name yfinance_tool --force

# Phase 2: Tool creation (uses LLM to generate code)
uv run python -m toolmaker create task_yfinance --name yfinance_tool --force
```

**Issue encountered:** Docker image `ghcr.io/katherlab/toolmaker:cpu` was not available in the local registry.

```
ImageNotFound: 404 Client Error for http+docker://localhost/v1.54/images/ghcr.io/katherlab/toolmaker:cpu/json: 
Not Found ("No such image: ghcr.io/katherlab/toolmaker:cpu")
```

This indicates that while the TOOLMAKER framework is properly configured and task definitions are valid, we encountered an infrastructure blockers at the containerization layer.

### 3.3 Schema Validation & Intermediate Milestones

Despite the Docker issue, we verified:
- ✅ All 3 `task.yaml` files pass ToolArena schema validation
- ✅ Task definitions include required metadata (name, repo, papers, category, arguments, returns, example)
- ✅ Example invocations correctly specify argument types and values

**Example task.yaml (yfinance):**
```yaml
name: yfinance_fetch_prices
repo:
  name: yfinance
  url: https://github.com/ranaroussi/yfinance
category: financial_data
description: Fetch historical daily closing prices for a given stock ticker and date range.
arguments:
  - name: ticker
    type: str
    description: Stock ticker symbol (e.g., AAPL, GOOGL)
  - name: start_date
    type: str
    description: Start date in YYYY-MM-DD format
example:
  arguments:
    - name: ticker
      value: "AAPL"
    - name: start_date
      value: "2023-01-01"
```

---

## 4. Challenges & Mitigations

### 4.1 Docker Image Availability

**Challenge:** The specified TOOLMAKER Docker image was not available in the local environment, blocking the environment installation phase.

**Root Cause:** The image must be explicitly pulled via `docker pull ghcr.io/katherlab/toolmaker:cpu` before TOOLMAKER can containerize the financial repositories.

**Mitigation Plan:** 
- Ensure Docker daemon is running and connected to GitHub Container Registry
- Pull both CPU and CUDA images as specified in TOOLMAKER README
- Retry tool creation pipeline once images are cached locally

### 4.2 Free-Tier API Quota Management

**Challenge:** Using a free-tier Gemini API key limits request throughput and total monthly quota.

**Current Status:** 
- Key is configured in `.env` (GEMINI_API_KEY)
- LiteLLM handles rate-limiting via tenacity retry logic
- We have not yet incurred significant costs due to tool creation delays

**Mitigation Plan:**
- Monitor API usage via Google Cloud Console
- Implement request batching for parallel tool creation
- Consider fallback to local models if API quota is exhausted

### 4.3 Task Definition Schema Complexity

**Challenge:** ToolArena schema requires multiple fields (name, repo dict, papers list, category, arguments array, returns array, example invocation), which took iteration to get correct.

**Mitigation:** Created template-based task definitions with all required fields to ensure valid YAML structure upfront.

---

## 5. Timeline and Contributions

### 5.1 Project Timeline

| Phase | Target Dates | Deliverable | Status |
|---|---|---|---|
| **Phase 1: Planning** | Apr 29 – May 6 | Interest form, repo selection | ✅ Complete |
| **Phase 2: Setup** | May 7 – May 13 | Task definitions, API config | ✅ Complete |
| **Phase 3: Baseline Runs** | May 14 – May 18 | Baseline tool creation logs | 🔄 In Progress (Docker blocker) |
| **Phase 4: Benchmarking** | May 19 – May 26 | Success rates, failure analysis | 📅 Planned |
| **Phase 5: Writeup** | May 27 – June 2 | Final 5-page report | 📅 Planned |

### 5.2 Individual Contributions

| Member | Responsibilities | Contribution |
|---|---|---|
| **Amal Padhye** | Repository curation; task.yaml schema design and validation; documentation | 33% |
| **Connor Wang** | Docker & LiteLLM proxy configuration; infrastructure setup; API key management | 33% |
| **Nicholas Jiang** | TOOLMAKER pipeline debugging; report drafting; LLM integration testing | 33% |

---

## 6. Deviations from Presentation

Our presentation proposed testing **five representative financial repositories**; however, we adjusted the scope to **three focus repositories** to ensure:
- High-quality, reproducible task definitions within API quota constraints
- Sufficient time to diagnose and document infrastructure issues
- Clear analysis of success/failure patterns without diluting effort

This represents a deliberate scope reduction in line with research best practices: better to deeply understand 3 well-specified tasks than to shallowly sample 5.

---

## References

Wölflein, G., Ferber, D., Truhn, D., Arandjelović, O., & Kather, J. N. (2025). LLM Agents Making Agent Tools. In *Proceedings of the Annual Meeting of the Association for Computational Linguistics (ACL)*, July 2025.

