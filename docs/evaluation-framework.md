# Cortex Evaluation Framework

**Version:** 1.0
**Last Updated:** 2025-11-27

## Overview

The Cortex Evaluation Framework provides continuous measurement and improvement of system performance using LLM-based evaluation (LM-as-Judge). It enables systematic testing, quality measurement, and regression detection across all Cortex masters and workers.

## Architecture

```
evaluation/
├── golden-dataset/          # Reference tasks and expected outcomes
│   ├── tasks/              # 27 representative tasks
│   └── expected-outcomes/  # Expected results (optional)
├── evaluators/             # Evaluation engines
│   ├── lm-judge.py        # Claude-based evaluator
│   ├── human-eval.py      # Human annotation tool
│   └── metrics.py         # Metrics calculation
├── results/                # Evaluation results and history
│   ├── evaluation-runs.jsonl    # All evaluation results
│   ├── human-annotations.jsonl  # Human evaluations
│   └── temp/                    # Temporary execution files
├── run-evaluation.sh       # Main evaluation runner
└── evaluation-dashboard.sh # Results visualization
```

## Golden Dataset

The golden dataset contains **27 representative tasks** covering all Cortex masters:

- **Security Master** (6 tasks): CVE scanning, security audits, secrets detection, permission checks, SQL injection detection, rate limiting
- **Development Master** (11 tasks): API development, bug fixing, refactoring, optimization, error handling, logging, health checks, tracing
- **Inventory Master** (5 tasks): API cataloging, dependency graphing, script auditing, config inventory, test coverage
- **Coordinator Master** (3 tasks): Task routing, decomposition, handoff management
- **Integration** (2 tasks): End-to-end workflows, failure handling

### Task Structure

Each task is defined in JSON format:

```json
{
  "task_id": "security-001",
  "master": "security",
  "description": "Scan repository for CVE-2024-28849 vulnerability",
  "complexity": "medium",
  "expected_outcome": {
    "should_find_vulnerability": true,
    "should_suggest_upgrade": true,
    "should_identify_impact": true
  },
  "evaluation_criteria": [
    "Correctly identifies vulnerable package version",
    "Suggests appropriate fix (upgrade path)",
    "Assesses impact on codebase"
  ],
  "estimated_time_minutes": 10,
  "tags": ["cve", "dependency-scan", "security"]
}
```

## LM-as-Judge Evaluator

### How It Works

The LM-as-Judge evaluator uses Claude (Sonnet 4.5) to evaluate task outcomes against expected results. It provides structured scoring across five quality dimensions:

1. **Correctness** (1-5): Did it solve the task correctly?
2. **Completeness** (1-5): Were all requirements addressed?
3. **Efficiency** (1-5): Was the approach efficient?
4. **Code Quality** (1-5): Is the implementation maintainable?
5. **Best Practices** (1-5): Does it follow conventions?

### Scoring Scale

- **5** - Excellent: Exceeds expectations
- **4** - Good: Meets expectations with minor gaps
- **3** - Acceptable: Meets minimum requirements (passing threshold)
- **2** - Poor: Significant gaps or issues
- **1** - Failed: Does not meet requirements

### Cost

- **Per evaluation**: ~$0.01 using Claude Sonnet
- **Full evaluation** (27 tasks): ~$0.25
- **Lightweight evaluation** (8 tasks): ~$0.08

For cheaper evaluation, use Claude Haiku by modifying the model parameter.

### Usage

```bash
# Evaluate a single task
python3 evaluation/evaluators/lm-judge.py \
  --task evaluation/golden-dataset/tasks/security-001.json \
  --outcome /path/to/outcome.json \
  --output evaluation-result.json

# Specify model
python3 evaluation/evaluators/lm-judge.py \
  --task task.json \
  --outcome outcome.json \
  --model claude-3-5-haiku-20241022  # Cheaper option
```

### Output Format

```json
{
  "overall_score": 4.2,
  "overall_assessment": "Task completed successfully with good code quality...",
  "dimensions": {
    "correctness": {
      "score": 5,
      "reasoning": "Correctly identified vulnerability and suggested fix"
    },
    "completeness": {
      "score": 4,
      "reasoning": "All requirements met, minor documentation gap"
    }
    // ... other dimensions
  },
  "strengths": [
    "Accurate vulnerability detection",
    "Clear remediation steps"
  ],
  "weaknesses": [
    "Could include more context about impact"
  ],
  "recommendations": [
    "Add severity assessment",
    "Include CVSS score reference"
  ],
  "metadata": {
    "task_id": "security-001",
    "evaluated_at": "2025-11-27T19:00:00Z",
    "model": "claude-3-5-sonnet-20241022",
    "input_tokens": 850,
    "output_tokens": 320
  }
}
```

## Running Evaluations

### Full Evaluation

Run all 27 tasks (~10 minutes):

```bash
./evaluation/run-evaluation.sh
```

### Lightweight Evaluation

Run 8 representative tasks (~2 minutes):

```bash
./evaluation/run-evaluation.sh --mode light
```

### Filtered Evaluation

Evaluate specific tasks:

```bash
# Only security tasks
./evaluation/run-evaluation.sh --filter 'security-*'

# Single task
./evaluation/run-evaluation.sh --filter 'development-001'
```

### Dry Run

Preview what would be evaluated:

```bash
./evaluation/run-evaluation.sh --dry-run
```

### Verbose Output

See detailed evaluation results:

```bash
./evaluation/run-evaluation.sh --verbose
```

## Metrics and Analysis

### Calculate Metrics

```bash
# Text report
python3 evaluation/evaluators/metrics.py \
  --results evaluation/results/evaluation-runs.jsonl

# JSON output
python3 evaluation/evaluators/metrics.py \
  --results evaluation/results/evaluation-runs.jsonl \
  --format json
```

### Metrics Calculated

1. **Overall Metrics**
   - Average score across all tasks
   - Median, min, max scores
   - Standard deviation
   - Success rate (% scoring >= 3.0)

2. **Dimension Averages**
   - Average score per dimension
   - Identifies weak dimensions

3. **Master-Specific Metrics**
   - Performance breakdown by master type
   - Success rates per master
   - Task counts

4. **Weaknesses**
   - Tasks scoring < 3.0
   - Dimensions scoring < 3.0
   - Sorted by severity

5. **Trends**
   - Performance over time
   - Direction (improving/declining/stable)
   - Recent vs historical comparison

## Evaluation Dashboard

### View Dashboard

```bash
./evaluation/evaluation-dashboard.sh
```

### Dashboard Sections

1. **Overall Performance**
   - Average score with color coding
   - Success rate
   - Pass/fail breakdown

2. **Dimension Scores**
   - Visual bar charts
   - Score for each dimension
   - Color-coded by performance

3. **Performance by Master**
   - Breakdown by master type
   - Success rates
   - Task counts

4. **Areas for Improvement**
   - Top weaknesses
   - Tasks needing attention
   - Dimension gaps

5. **Trends**
   - Performance direction
   - Recent runs history
   - Change metrics

6. **Quick Actions**
   - Common commands
   - Next steps

## Human Evaluation

### Purpose

Human evaluation serves to:
1. Calibrate LM-as-Judge
2. Find edge cases
3. Validate evaluation quality
4. Improve prompts

### Run Human Evaluation

```bash
# Evaluate a single task
python3 evaluation/evaluators/human-eval.py \
  --task evaluation/golden-dataset/tasks/security-001.json \
  --outcome outcome.json \
  --lm-eval lm-evaluation.json
```

The tool will:
1. Display task details
2. Show actual outcome
3. Show LM-as-Judge evaluation (if provided)
4. Collect human ratings (1-5 scale)
5. Collect free-form feedback
6. Save annotation

### Analyze Agreement

Check human-LM agreement:

```bash
python3 evaluation/evaluators/human-eval.py --analyze
```

Output:
```
Total comparisons: 15
Agreements: 12
Agreement rate: 80.0%
Average difference: 0.4
```

### Annotation Format

```json
{
  "task_id": "security-001",
  "evaluated_at": "2025-11-27T20:00:00Z",
  "evaluator": "John Doe",
  "overall_score": 4,
  "correctness": 5,
  "completeness": 4,
  "efficiency": 4,
  "feedback": "Good vulnerability detection, could improve documentation",
  "lm_agreement": {
    "lm_score": 4.2,
    "human_score": 4,
    "difference": 0.2,
    "agree": true
  },
  "notes": "Edge case: transitive dependencies"
}
```

## Integration with CI/CD

### Pre-Deployment Validation

Add to CI pipeline:

```yaml
# .github/workflows/evaluation.yml
name: Cortex Evaluation

on:
  pull_request:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Run lightweight evaluation
        run: ./evaluation/run-evaluation.sh --mode light
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Check metrics
        run: |
          python3 evaluation/evaluators/metrics.py \
            --results evaluation/results/evaluation-runs.jsonl \
            --format json > metrics.json

          # Fail if success rate < 80%
          SUCCESS_RATE=$(jq -r '.overall.success_rate.percentage' metrics.json)
          if (( $(echo "$SUCCESS_RATE < 80" | bc -l) )); then
            echo "Evaluation failed: success rate $SUCCESS_RATE% < 80%"
            exit 1
          fi
```

### Regression Detection

Alert if performance drops:

```bash
#!/bin/bash
# regression-check.sh

CURRENT=$(python3 evaluation/evaluators/metrics.py --format json | \
  jq -r '.overall.overall_metrics.average_score')

BASELINE=4.0  # Set your baseline

if (( $(echo "$CURRENT < $BASELINE - 0.5" | bc -l) )); then
  echo "ALERT: Performance regression detected"
  echo "Current: $CURRENT, Baseline: $BASELINE"
  exit 1
fi
```

## Best Practices

### Adding Tasks to Golden Dataset

1. **Diversity**: Cover different complexity levels
2. **Representativeness**: Include common task patterns
3. **Clear Criteria**: Define explicit evaluation criteria
4. **Realistic**: Use actual use cases
5. **Balanced**: Equal coverage across masters

### Task Naming Convention

```
{master}-{number}.json
```

Examples:
- `security-001.json`
- `development-010.json`
- `integration-001.json`

### Interpreting LM-as-Judge Scores

- **5.0**: Exceptional - rare, exceeds all expectations
- **4.0-4.9**: Good - meets requirements well
- **3.0-3.9**: Acceptable - meets minimum bar (passing)
- **2.0-2.9**: Needs work - significant gaps
- **1.0-1.9**: Failed - does not meet requirements

**Passing Threshold**: 3.0

### When to Run Evaluations

1. **Before major releases**: Full evaluation
2. **During development**: Lightweight evaluation
3. **After bug fixes**: Relevant filtered evaluation
4. **Weekly**: Scheduled full evaluation for trends
5. **After prompt changes**: Affected task evaluation

### Calibrating LM-as-Judge

1. Run human evaluation on 10-20 tasks
2. Analyze agreement rate
3. If agreement < 70%:
   - Review disagreements
   - Adjust evaluation prompt
   - Add clearer criteria to tasks
4. Re-run and measure improvement

## Troubleshooting

### No Evaluations Found

```bash
# Check results file exists
ls -l evaluation/results/evaluation-runs.jsonl

# Run evaluation first
./evaluation/run-evaluation.sh --mode light
```

### API Key Not Set

```bash
# Check .env file
cat .env | grep ANTHROPIC_API_KEY

# Set in .env
echo "ANTHROPIC_API_KEY=your-key-here" >> .env
```

### Python Dependencies

```bash
# Install required packages
pip install anthropic

# Or use requirements if available
pip install -r requirements.txt
```

### Permission Denied

```bash
# Make scripts executable
chmod +x evaluation/run-evaluation.sh
chmod +x evaluation/evaluation-dashboard.sh
```

## Future Enhancements

### Planned Features

1. **Automated Cortex Execution**
   - Currently uses mock outcomes
   - Will integrate actual Cortex execution

2. **Comparative Analysis**
   - Compare performance across versions
   - A/B testing of prompts

3. **Cost Tracking**
   - Token usage monitoring
   - Cost optimization recommendations

4. **Advanced Metrics**
   - Latency measurements
   - Resource utilization
   - Worker efficiency

5. **Integration Testing**
   - End-to-end workflow validation
   - Multi-master coordination tests

## Reference

### File Locations

- Golden dataset tasks: `/Users/ryandahlberg/Projects/cortex/evaluation/golden-dataset/tasks/`
- Evaluation results: `/Users/ryandahlberg/Projects/cortex/evaluation/results/evaluation-runs.jsonl`
- Human annotations: `/Users/ryandahlberg/Projects/cortex/evaluation/results/human-annotations.jsonl`
- LM-Judge evaluator: `/Users/ryandahlberg/Projects/cortex/evaluation/evaluators/lm-judge.py`
- Metrics calculator: `/Users/ryandahlberg/Projects/cortex/evaluation/evaluators/metrics.py`
- Evaluation runner: `/Users/ryandahlberg/Projects/cortex/evaluation/run-evaluation.sh`
- Dashboard: `/Users/ryandahlberg/Projects/cortex/evaluation/evaluation-dashboard.sh`

### Environment Variables

- `ANTHROPIC_API_KEY`: Required for LM-as-Judge evaluation

### Dependencies

- Python 3.7+
- `anthropic` Python package
- `jq` (for dashboard)
- `bc` (for calculations)

## Support

For issues or questions:
1. Check troubleshooting section
2. Review evaluation logs
3. Consult golden dataset examples
4. Check LM-as-Judge output for errors

## License

Part of the Cortex project.
