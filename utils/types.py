from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Set

@dataclass
class APIMethod:
    """Represents an API method discovered in the source code.
    
    This class stores metadata about an API method that is extracted during
    source code analysis and used for documentation generation.
    
    Attributes:
        name (str): Name of the method
        module (str): Full module path where the method is defined
        docstring (Optional[str]): Method's docstring if present
        signature (str): Method signature including parameters
        path (Path): Path to the source file containing the method
        description (Optional[str]): Human-readable description of the method
        parameters (Optional[Dict[str, str]]): Parameter names and types
        return_type (Optional[str]): Return type of the method
    """
    name: str
    module: str
    docstring: Optional[str]
    signature: str
    path: Path
    description: Optional[str] = None
    parameters: Optional[Dict[str, str]] = None
    return_type: Optional[str] = None

@dataclass
class CodeExample:
    """Represents a generated code example with optional test code.
    
    Stores a complete code example including description, code snippet,
    expected output, and optionally a unit test.
    
    Attributes:
        description (str): Description of what the example demonstrates
        code (str): The example code snippet
        output (str): Expected output when running the code
        test_code (Optional[str]): Generated unit test for the example
    """
    description: str
    code: str
    output: str
    test_code: Optional[str] = None

@dataclass
class SphinxConfig:
    """Configuration settings for Sphinx documentation generation.
    
    This class stores all configuration needed to generate Sphinx documentation,
    including paths, project metadata, and Sphinx-specific settings.
    
    Attributes:
        project_name (str): Name of the project being documented
        author (str): Author/owner of the project
        version (str): Version of the project
        source_dir (Path): Directory containing the source code to document
        docs_dir (Path): Directory where Sphinx files will be generated
        output_dir (Path): Directory for the built HTML documentation
        theme (str): Sphinx theme to use, defaults to "sphinx_rtd_theme"
        extensions (List[str]): List of Sphinx extensions to enable
    
    Example:
        ```python
        config = SphinxConfig(
            project_name="MyProject",
            author="Dev Team",
            version="1.0.0",
            source_dir=Path("./src"),
            docs_dir=Path("./docs"),
            output_dir=Path("./docs/html")
        )
        ```
    """
    project_name: str
    author: str
    version: str
    source_dir: Path
    docs_dir: Path
    output_dir: Path
    theme: str = "sphinx_rtd_theme"
    extensions: List[str] = None

    def __post_init__(self):
        if self.extensions is None:
            self.extensions = [
                'sphinx.ext.autodoc',
                'sphinx.ext.napoleon',
                'sphinx.ext.viewcode',
                'sphinx.ext.intersphinx',
                'sphinx_rtd_theme',
            ] 

@dataclass
class TestGenerationResult:
    """Result of generating and validating a single API method's tests.
    
    Attributes:
        method_name (str): Name of the API method
        test_file_path (str): Path to the generated test file
        passed_validation (bool): Whether the test passed validation
        coverage_percentage (float): Test coverage percentage
        error_message (Optional[str]): Error message if validation failed
    """
    method_name: str
    test_file_path: str
    passed_validation: bool
    coverage_percentage: float
    error_message: Optional[str] = None

@dataclass
class TestResults:
    """Results from running example code tests.
    
    Attributes:
        all_passed (bool): Whether all tests passed
        failures (List[str]): List of failure messages
        total_tests (int): Total number of tests run
        passed_tests (int): Number of tests that passed
    """
    all_passed: bool
    failures: List[str]
    total_tests: int
    passed_tests: int

    def __len__(self):
        return len(self.failures)

@dataclass
class ValidationResult:
    """Result of validating API documentation against source code.
    
    Attributes:
        is_valid (bool): Whether the documentation is valid
        errors (List[str]): List of validation errors found
        suggestions (List[str]): List of improvement suggestions
    """
    is_valid: bool
    errors: List[str]
    suggestions: List[str]
