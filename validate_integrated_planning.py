"""Run integrated cross-phase validation and write one evidence JSON file."""

from __future__ import annotations

import sys

from shared.validation.integrated_validation import write_integrated_validation


def main() -> None:
    evidence_path, report_path, evidence = write_integrated_validation()
    result = evidence["overall_result"]
    print(f"Integrated validation evidence: {evidence_path}")
    print(f"Integrated validation report: {report_path}")
    print(f"Overall status: {result['status']}")
    print(f"PASS count: {result['pass_count']}")
    print(f"WARNING count: {result['warning_count']}")
    print(f"FAIL count: {result['fail_count']}")
    print(f"SKIPPED count: {result['skipped_count']}")
    if int(result["fail_count"]) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
