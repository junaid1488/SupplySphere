from pathlib import Path
import subprocess, sys

root=Path(__file__).resolve().parents[1]
result=subprocess.run([sys.executable,"-m","pytest","-q"],cwd=root,text=True,capture_output=True)
audit=root/"FINAL_AUDIT.md"
audit.write_text(f'''# SupplySphere Phase 0–5 Final Audit

## Scope
Production foundation for PRD Phases 0–5: repository architecture, Olist ingestion,
PostgreSQL/data-quality foundation, analytics, deterministic synthetic supply chain, and demand forecasting.

## Automated Verification
Command: `python -m pytest -q`

Exit code: `{result.returncode}`

### Test output
```text
{result.stdout}
{result.stderr}
```

## Result
{"PASS — all automated tests passed." if result.returncode == 0 else "FAIL — one or more automated tests failed; review the output above."}

## Data Verification Boundary
No claim is made here that a trained forecasting model has production accuracy unless the real Olist
dataset is present and a training run has been executed. The repository contains deterministic fixtures
for automated tests and a real-data training pipeline for Phase 5.

## Production Readiness Boundary
This archive implements Phases 0–5. Phases 6–17 remain outside this build and are not represented as completed.
''',encoding="utf-8")
print(audit)
raise SystemExit(result.returncode)
