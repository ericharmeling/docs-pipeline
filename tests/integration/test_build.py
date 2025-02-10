import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, AsyncMock, patch
from build.build import DocumentationBuilder, RepoConfig
import logging
import json

@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def mock_repo_structure(temp_workspace):
    """Create mock repository structure."""
    # Create source files but don't place them yet
    content = {
        "src/api.py": """
def example_function(param: str) -> str:
    \"\"\"Example function for testing.
    
    Args:
        param: Input parameter
        
    Returns:
        str: Processed result
    \"\"\"
    return f"Hello {param}"
    """,
        "docs/source/conf.py": """
project = 'Test API'
copyright = '2024'
author = 'Test Author'
extensions = ['sphinx.ext.autodoc']
templates_path = ['_templates']
exclude_patterns = []
html_theme = 'alabaster'
""",
        "docs/source/index.rst": """
Welcome to Test API documentation!
================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   example_function
"""
    }
    
    return content

@pytest.fixture
def setup_workspace(temp_workspace):
    """Setup required workspace structure."""
    # Create all required directories
    dirs = [
        "repo",
        "src",
        "docs/source",
        "docs/html",
        ".cache"
    ]
    for dir_path in dirs:
        (temp_workspace / dir_path).mkdir(parents=True, exist_ok=True)
    
    return temp_workspace

@pytest.fixture
def mock_git(mock_repo_structure):
    """Mock git operations."""
    with patch("git.Repo") as mock_repo:
        def mock_clone(url, to_path, **kwargs):
            print("\n=== Debug: mock_clone called ===")
            print(f"to_path: {to_path}")
            
            # Create files directly in workspace src directory
            workspace_dir = Path(to_path).parent
            print(f"workspace_dir: {workspace_dir}")
            
            # List existing directories
            print("\nExisting directories before:")
            for p in workspace_dir.glob("**/*"):
                print(f"  {p}")
            
            for file_path, content in mock_repo_structure.items():
                if file_path.startswith("src/"):
                    # Remove "src/" prefix since we're already in src directory
                    relative_path = file_path[4:]
                    dest_path = workspace_dir / "src" / relative_path
                    
                    # Only create file if it doesn't exist
                    if not dest_path.exists():
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        dest_path.write_text(content)
                        print(f"\nCreated source file: {dest_path}")
                    else:
                        print(f"\nSkipping existing file: {dest_path}")
                else:
                    # Other files go in their normal location
                    dest_path = workspace_dir / file_path
                    if not dest_path.exists():
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        dest_path.write_text(content)
                        print(f"\nCreated other file: {dest_path}")
                        
                        if file_path.endswith("index.rst"):
                            example_rst = dest_path.parent / "example_function.rst"
                            if not example_rst.exists():
                                example_rst.parent.mkdir(parents=True, exist_ok=True)
                                example_rst.write_text("""
Example Function
===============

.. autofunction:: example_function
""")
                                print(f"Created example RST: {example_rst}")
                    else:
                        print(f"\nSkipping existing file: {dest_path}")
            
            # List files after creation
            print("\nExisting files after:")
            for p in workspace_dir.glob("**/*"):
                print(f"  {p}")
            
            return mock_repo.return_value

        mock_repo.clone_from = Mock(side_effect=mock_clone)
        yield mock_repo

@pytest.fixture
def mock_claude():
    """Mock Claude API responses."""
    with patch("anthropic.Client") as mock_client:
        client_instance = Mock()
        messages = AsyncMock()
        message = Mock()
        message.content = [{
            "type": "text",
            "text": "VALID\nNo errors found\nSUGGESTIONS:\n- None"
        }]
        messages.create.return_value = message
        client_instance.messages = messages
        mock_client.return_value = client_instance
        yield mock_client

@pytest.mark.asyncio
async def test_successful_build_and_cleanup(setup_workspace, mock_repo_structure, mock_git, mock_claude):
    """Test a complete build cycle including cleanup.
    
    Verifies that:
    1. Documentation is generated successfully
    2. Reports are generated in permanent location
    3. Temporary files are cleaned up
    """
    builder = DocumentationBuilder(
        api_key="test-key",
        repo_configs=[RepoConfig(
            url="https://github.com/test/repo.git",
            paths=["src"]
        )],
        temp_dir=setup_workspace
    )
    
    # Run build
    result = await builder.build()
    
    # Verify build success
    assert result.validation_passed, f"Build failed with error: {result.error_message}"
    assert result.tests_passed
    assert mock_claude.return_value.messages.create.called, "Documentation was not validated"
    
    # Verify permanent artifacts in docs directory
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # Check HTML output
    html_dir = docs_dir / "html"
    assert html_dir.exists(), "HTML output directory not found"
    assert (html_dir / "index.html").exists(), "Generated HTML not found"
    
    # Check reports
    reports_dir = docs_dir / "reports"
    assert reports_dir.exists(), "Reports directory not found"
    assert (reports_dir / "test_report.md").exists(), "Test report not found"
    assert (reports_dir / "validation_report.md").exists(), "Validation report not found"
    
    # Run cleanup and verify temp files are gone
    builder.cleanup()
    assert not setup_workspace.exists(), "Temporary workspace was not cleaned up"

@pytest.mark.asyncio
async def test_incremental_and_change_detection(temp_workspace, mock_repo_structure, mock_git, mock_claude, caplog):
    """Test build behavior with caching and file changes."""
    caplog.set_level(logging.DEBUG)
    
    # Create permanent directories
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "reports").mkdir(parents=True, exist_ok=True)
    (docs_dir / "html").mkdir(parents=True, exist_ok=True)
    
    builder = DocumentationBuilder(
        api_key="test-key",
        repo_configs=[RepoConfig(url="https://github.com/test/repo.git")],
        temp_dir=temp_workspace
    )
    
    # First build
    result1 = await builder.build()
    assert result1.validation_passed
    
    # Verify cache was written with content hashes
    cache_file = Path(".cache/build_state.json")
    assert cache_file.exists(), "Cache file was not created"
    cache_data = json.loads(cache_file.read_text())
    assert len(cache_data) > 0, "Cache is empty"
    
    # Save content hashes from first build
    original_hashes = {path: state['content_hash'] for path, state in cache_data.items()}
    
    # Second build - should use cache since content hasn't changed
    mock_claude.return_value.messages.create.reset_mock()
    result2 = await builder.build()
    assert result2.validation_passed
    
    # Verify hashes haven't changed
    cache_data = json.loads(cache_file.read_text())
    assert all(
        cache_data[path]['content_hash'] == original_hashes[path]
        for path in original_hashes
    ), "File content hashes changed when they shouldn't have"
    
    # Verify cache was used
    assert not mock_claude.return_value.messages.create.called, "Cache was not used for unchanged files"

@pytest.mark.asyncio
async def test_build_with_validation_errors(temp_workspace, mock_repo_structure, mock_git, mock_claude):
    """Test build process when validation fails."""
    
    # Override the default mock response for this test
    message = Mock()
    message.content = [
        {
            "type": "text",
            "text": "INVALID\nERRORS:\n- Parameter mismatch\nSUGGESTIONS:\n- Update docs"
        }
    ]
    mock_claude.return_value.messages.create.return_value = message
    
    builder = DocumentationBuilder(
        api_key="test-key",
        repo_configs=[RepoConfig(url="https://github.com/test/repo.git")],
        temp_dir=temp_workspace  # Pass temp_dir during initialization
    )
    
    result = await builder.build()
    
    assert not result.validation_passed
    assert "Parameter mismatch" in str(result.error_message)

@pytest.mark.asyncio
async def test_build_with_multiple_repos(temp_workspace, mock_repo_structure, mock_git, mock_claude):
    """Test building docs from multiple repositories."""
    builder = DocumentationBuilder(
        api_key="test-key",
        repo_configs=[
            RepoConfig(url="https://github.com/test/repo1.git"),
            RepoConfig(url="https://github.com/test/repo2.git")
        ],
        temp_dir=temp_workspace
    )
    
    result = await builder.build()
    assert result.validation_passed
    assert mock_git.clone_from.call_count == 2 

@pytest.fixture(autouse=True)
def setup_cache_dir():
    """Ensure cache directory exists before each test."""
    cache_dir = Path(".cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    yield
    # Don't clean up cache after tests 