import logging
from pathlib import Path
from typing import List, Dict, Optional
import pytest
import coverage
from utils.types import APIMethod, CodeExample, TestGenerationResult, TestResults
from utils.example_generator import ExampleGenerator
import tempfile
import time

class TestGenerationWorkflow:
    """Handles generation and execution of tests for API examples.
    
    This class manages the test environment, runs tests for generated examples,
    and reports on test results.
    
    Example:
        ```python
        workflow = TestGenerationWorkflow(api_key)
        results = await workflow.run_tests(api_methods, examples_by_method)
        
        if not results.all_passed:
            print("Test failures:")
            for failure in results.failures:
                print(f"- {failure}")
        ```
    """

    def __init__(self, api_key: str, temp_dir: Optional[Path] = None):
        """Initialize the test workflow.
        
        Args:
            api_key: Claude API key for test generation
            temp_dir: Optional temporary directory for test files
        """
        self.api_key = api_key
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp())
        self.logger = logging.getLogger(__name__)
        self.example_generator = ExampleGenerator(api_key)
        
        # Create test directory if it doesn't exist
        self.test_dir = self.temp_dir / "tests"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
    async def setup_test_environment(self):
        """Prepare the test environment.
        
        Creates necessary directories and configuration files for testing.
        """
        self.test_dir.mkdir(parents=True, exist_ok=True)
        (self.test_dir / "__init__.py").touch()
        
        pytest_ini = Path("pytest.ini")
        if not pytest_ini.exists():
            pytest_ini.write_text("""
[pytest]
asyncio_mode = auto
python_files = test_*.py
python_functions = test_*
addopts = -v --cov=src --cov-report=term-missing
""")

    async def run_tests(self, api_methods: List[APIMethod], 
                       examples_by_method: Dict[str, List[CodeExample]]) -> List[bool]:
        """Run tests for all example code."""
        await self.setup_test_environment()
        
        test_results = []
        for method in api_methods:
            examples = examples_by_method.get(method.name, [])
            for example in examples:
                if example.test_code:
                    result = await self._run_test(method, example)
                    test_results.append(result["passed"])
        
        return test_results

    async def _run_test(self, method: APIMethod, example: CodeExample) -> dict:
        """Run a single test for an example."""
        test_path = self.test_dir / f"test_{method.name}_{int(time.time()*1000)}.py"
        try:
            test_path.write_text(example.test_code)
            result = await self._validate_test(test_path)
            return {
                "passed": result.passed_validation,
                "error": result.error_message,
                "method": method.name,
                "example": example.description
            }
        finally:
            if test_path.exists():
                try:
                    test_path.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup test file {test_path}: {e}")

    async def _validate_test(self, test_path: Path) -> TestGenerationResult:
        """Run pytest on a test file and collect results."""
        cov = coverage.Coverage()
        cov.start()
        
        try:
            exit_code = pytest.main([
                str(test_path),
                "-v",
                "--disable-warnings"
            ])
            
            cov.stop()
            cov.save()
            
            coverage_percentage = cov.report(include=str(test_path))
            
            return TestGenerationResult(
                method_name=test_path.stem.replace("test_", ""),
                test_file_path=str(test_path),
                passed_validation=exit_code == 0,
                coverage_percentage=coverage_percentage,
                error_message=None if exit_code == 0 else f"Tests failed with exit code {exit_code}"
            )
            
        except Exception as e:
            return TestGenerationResult(
                method_name=test_path.stem.replace("test_", ""),
                test_file_path=str(test_path),
                passed_validation=False,
                coverage_percentage=0.0,
                error_message=str(e)
            )

    def _compile_results(self, test_results: List[dict]) -> TestResults:
        """Compile individual test results into a TestResults object."""
        failures = []
        passed = 0
        total = len(test_results)

        for result in test_results:
            if result["passed"]:
                passed += 1
            else:
                failures.append(
                    f"{result['method']} - {result['example']}: {result['error']}"
                )

        return TestResults(
            all_passed=passed == total,
            failures=failures,
            total_tests=total,
            passed_tests=passed
        ) 