from pathlib import Path
import json
import logging
from datetime import datetime
from typing import List, Dict
from dataclasses import dataclass
from utils.types import TestGenerationResult, ValidationResult

@dataclass
class ReportConfig:
    """Configuration for report generation.
    
    Attributes:
        output_dir: Directory where reports will be saved
        project_name: Name of the project
        version: Project version
    """
    output_dir: Path = Path("docs/reports")
    project_name: str = "API Documentation"
    version: str = "1.0.0"

class ReportGenerator:
    """Generates documentation and test reports.
    
    This class handles creating various reports including:
    - Test execution results
    - Documentation validation status
    - Coverage metrics
    
    Example:
        ```python
        generator = ReportGenerator()
        
        # Generate test report
        await generator.generate_test_report(test_results)
        
        # Generate validation report
        await generator.generate_validation_report(validation_results)
        ```
    """
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    async def generate_test_report(self, results: List[bool]):
        """Generate test execution report."""
        try:
            # Use permanent reports directory
            reports_dir = Path("docs/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_path = reports_dir / "test_report.md"
            
            # Generate report content
            report = [
                "# Test Execution Report\n",
                f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                "## Summary\n",
                f"- Total Tests: {len(results)}\n",
                f"- Passed: {sum(results)}\n",
                f"- Failed: {len(results) - sum(results)}\n"
            ]
            
            # Save report
            report_path.write_text('\n'.join(report))
            
            self.logger.info(f"Generated test report at {report_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to generate test report: {e}")
            raise  # Add raise to match validation report behavior

    async def generate_validation_report(self, validation_results):
        """Generate a validation report from results."""
        try:
            reports_dir = Path("docs/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_path = reports_dir / "validation_report.md"
            
            # Generate report content
            report = [
                "# Documentation Validation Report\n",
                f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                "## Status\n",
                f"- Overall Status: {'✅ Valid' if validation_results.is_valid else '❌ Invalid'}\n"
            ]
            
            if validation_results.errors:
                report.extend([
                    "## Errors\n",
                    *[f"- {error}" for error in validation_results.errors],
                    ""
                ])
                
            if validation_results.suggestions:
                report.extend([
                    "## Suggestions\n",
                    *[f"- {suggestion}" for suggestion in validation_results.suggestions],
                    ""
                ])
            
            # Write report
            report_path.write_text('\n'.join(report))
            
        except Exception as e:
            self.logger.error(f"Failed to generate validation report: {e}")
            raise 