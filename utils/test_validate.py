import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from validate import APIValidator, APIDefinition, APIUsageExample

@pytest.fixture
def temp_dirs():
    """Create temporary directories for test files"""
    with tempfile.TemporaryDirectory() as api_dir, tempfile.TemporaryDirectory() as docs_dir:
        yield api_dir, docs_dir

@pytest.fixture
def sample_api_file(temp_dirs):
    """Create a sample API source file"""
    api_dir, _ = temp_dirs
    api_content = """
def example_function(param1: str, param2: int) -> bool:
    '''
    Example function docstring
    '''
    return True

def another_function(name: str) -> str:
    '''
    Another example function
    '''
    return f"Hello {name}"
    """
    
    file_path = Path(api_dir) / "sample_api.py"
    with open(file_path, "w") as f:
        f.write(api_content)
    return str(file_path)

@pytest.fixture
def sample_docs_file(temp_dirs):
    """Create a sample markdown documentation file"""
    _, docs_dir = temp_dirs
    docs_content = """
# API Documentation

Here's how to use the API:

```python
result = example_function("test", 42)
print(result)
```

Another example:
```python
greeting = another_function("Alice")
```

Invalid example:
```python
# This should raise a validation error
example_function(123)  # Wrong parameter type
```
"""
    
    file_path = Path(docs_dir) / "api_docs.md"
    with open(file_path, "w") as f:
        f.write(docs_content)
    return str(file_path)

@pytest.fixture
def validator(temp_dirs):
    """Create an APIValidator instance with mock Claude client"""
    api_dir, docs_dir = temp_dirs
    mock_client = Mock()
    mock_client.messages.create = AsyncMock()
    
    validator = APIValidator(
        api_source_dir=api_dir,
        docs_dir=docs_dir,
        claude_api_key="mock-key"
    )
    validator.client = mock_client
    return validator

def test_extract_api_definitions(validator, sample_api_file):
    """Test extraction of API definitions from source files"""
    validator.extract_api_definitions()
    
    assert len(validator.api_definitions) == 2
    
    # Check example_function definition
    example_func = validator.api_definitions["example_function"]
    assert isinstance(example_func, APIDefinition)
    assert example_func.name == "example_function"
    assert example_func.params == ["param1", "param2"]
    assert example_func.return_type == "bool"
    assert "Example function docstring" in example_func.docstring
    assert example_func.source_file == sample_api_file
    
    # Check another_function definition
    another_func = validator.api_definitions["another_function"]
    assert another_func.name == "another_function"
    assert another_func.params == ["name"]
    assert another_func.return_type == "str"

def test_extract_code_blocks(validator):
    """Test extraction of Python code blocks from markdown content"""
    markdown_content = """
# Test

```python
def test():
    pass
```

Some text

```python
print("hello")
```

```javascript
console.log("not python");
```
"""
    
    blocks = validator.extract_code_blocks(markdown_content)
    assert len(blocks) == 2  # Should only get Python blocks
    assert blocks[0][0] == "def test():\n    pass"
    assert blocks[1][0] == 'print("hello")'

def test_find_api_usage_examples(validator, sample_docs_file):
    """Test finding API usage examples in documentation"""
    # First populate api_definitions
    validator.api_definitions = {
        "example_function": APIDefinition(
            name="example_function",
            params=["param1", "param2"],
            return_type="bool",
            docstring="",
            source_file="",
            line_number=1
        ),
        "another_function": APIDefinition(
            name="another_function",
            params=["name"],
            return_type="str",
            docstring="",
            source_file="",
            line_number=1
        )
    }
    
    examples = validator.find_api_usage_examples()
    
    assert len(examples) == 3  # Should find all API usage examples
    
    # Verify first example
    assert any(
        ex.api_name == "example_function" and 
        'result = example_function("test", 42)' in ex.code_snippet
        for ex in examples
    )
    
    # Verify second example
    assert any(
        ex.api_name == "another_function" and 
        'greeting = another_function("Alice")' in ex.code_snippet
        for ex in examples
    )

@pytest.mark.asyncio
async def test_validate_usage_example(validator):
    """Test validation of API usage examples using mock Claude responses"""
    example = APIUsageExample(
        api_name="example_function",
        code_snippet='result = example_function("test", 42)',
        file_path="test.md",
        line_number=1
    )
    
    validator.api_definitions = {
        "example_function": APIDefinition(
            name="example_function",
            params=["param1", "param2"],
            return_type="bool",
            docstring="Test function",
            source_file="test.py",
            line_number=1
        )
    }
    
    # Mock Claude's response for valid usage
    validator.client.messages.create.return_value.content = "No issues found"
    issues = await validator.validate_usage_example(example)
    assert issues == ["No issues found"]
    
    # Mock Claude's response for invalid usage
    validator.client.messages.create.return_value.content = "1. Parameter type mismatch\n2. Wrong return value usage"
    issues = await validator.validate_usage_example(example)
    assert len(issues) == 2
    assert "Parameter type mismatch" in issues[0]
    assert "Wrong return value usage" in issues[1]

@pytest.mark.asyncio
async def test_validate_all(validator, sample_api_file, sample_docs_file):
    """Test end-to-end validation process"""
    # Mock Claude's responses
    validator.client.messages.create.return_value.content = "No issues found"
    
    results = await validator.validate_all()
    assert not results  # Should be empty when no issues found
    
    # Test with validation issues
    validator.client.messages.create.return_value.content = "Parameter type mismatch"
    results = await validator.validate_all()
    assert len(results) > 0  # Should contain validation issues
    
    # Verify results format
    for location, issues in results.items():
        assert isinstance(location, str)
        assert ":" in location  # Should be in format "file:line"
        assert isinstance(issues, list)
        assert all(isinstance(issue, str) for issue in issues) 