import ast
import glob
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
import anthropic
import logging
from utils.types import ValidationResult  # Import from types instead of defining locally

@dataclass
class APIDefinition:
    """Represents an API function/method definition found in source code.
    
    This class stores the complete definition of an API method extracted
    from source code analysis, including its signature and location.
    
    Attributes:
        name (str): Name of the API function/method
        params (List[str]): List of parameter names
        return_type (str): Return type annotation as a string
        docstring (str): Function's docstring if present
        source_file (str): Path to the file containing this API
        line_number (int): Line number where the function is defined
    """
    name: str
    params: List[str]
    return_type: str
    docstring: str
    source_file: str
    line_number: int

@dataclass
class APIUsageExample:
    """Represents an API usage example found in documentation.
    
    Stores information about where and how an API is used in documentation,
    allowing for validation of the usage against the actual API definition.
    
    Attributes:
        api_name (str): Name of the API being used
        code_snippet (str): The example code using the API
        file_path (str): Path to the documentation file
        line_number (int): Line number where the example appears
    """
    api_name: str
    code_snippet: str
    file_path: str
    line_number: int

class APIValidator:
    """Validates API documentation against source code using Claude.
    
    This class analyzes Python source code to extract API definitions and
    validates documentation examples against those definitions using the
    Anthropic Claude API.
    
    Example:
        ```python
        # Set up environment
        import os
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("Please set ANTHROPIC_API_KEY environment variable")
        
        # Initialize validator
        validator = APIValidator(
            api_source_dir="./src/api",
            docs_dir="./docs",
            claude_api_key=api_key
        )
        
        # Run validation
        results = await validator.validate_all()
        if results:
            print("Validation issues found:")
            for location, issues in results.items():
                print(f"{location}:")
                for issue in issues:
                    print(f"  - {issue}")
        else:
            print("All API usage examples are valid!")
        ```
    """
    def __init__(self, api_source_dir: str, docs_dir: str, claude_api_key: str):
        self.api_source_dir = api_source_dir
        self.docs_dir = docs_dir
        self.client = anthropic.Client(api_key=claude_api_key)
        self.api_definitions: Dict[str, APIDefinition] = {}
        self.logger = logging.getLogger(__name__)
        
    def extract_api_definitions(self) -> None:
        """Parse Python source files to extract API definitions.
        
        Recursively scans all Python files in api_source_dir to find and parse
        API function definitions using the ast module.
        
        The extracted definitions are stored in self.api_definitions, keyed by
        function name.
        
        Example:
            ```python
            validator.extract_api_definitions()
            for name, definition in validator.api_definitions.items():
                print(f"Found API: {name} in {definition.source_file}")
            ```
        """
        python_files = glob.glob(f"{self.api_source_dir}/**/*.py", recursive=True)
        
        for file_path in python_files:
            with open(file_path, 'r') as f:
                tree = ast.parse(f.read(), filename=file_path)
                
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    params = [arg.arg for arg in node.args.args]
                    return_type = (node.returns.id 
                                 if hasattr(node, 'returns') and node.returns 
                                 else 'None')
                    
                    self.api_definitions[node.name] = APIDefinition(
                        name=node.name,
                        params=params,
                        return_type=return_type,
                        docstring=ast.get_docstring(node) or '',
                        source_file=file_path,
                        line_number=node.lineno
                    )

    def extract_code_blocks(self, markdown_content: str) -> List[Tuple[str, int]]:
        """Extract Python code blocks from markdown content.
        
        Args:
            markdown_content (str): Markdown text to parse
            
        Returns:
            List[Tuple[str, int]]: List of tuples containing:
                - The code block content (str)
                - Starting position in the markdown (int)
        """
        pattern = r'```python\n(.*?)```'
        matches = re.finditer(pattern, markdown_content, re.DOTALL)
        return [(match.group(1).strip(), match.start()) for match in matches]

    def find_api_usage_examples(self) -> List[APIUsageExample]:
        """Scan markdown files for API usage examples.
        
        Recursively searches all markdown files in docs_dir for Python code blocks
        that contain calls to known API methods.
        
        Returns:
            List[APIUsageExample]: List of found API usage examples
            
        Example:
            ```python
            examples = validator.find_api_usage_examples()
            for ex in examples:
                print(f"Found usage of {ex.api_name} in {ex.file_path}")
            ```
        """
        markdown_files = glob.glob(f"{self.docs_dir}/**/*.md", recursive=True)
        usage_examples = []

        for file_path in markdown_files:
            with open(file_path, 'r') as f:
                content = f.read()
                
            code_blocks = self.extract_code_blocks(content)
            
            for code_block, position in code_blocks:
                # Find line number in the markdown file
                line_number = content[:position].count('\n') + 1
                
                # Look for API calls in the code block
                for api_name in self.api_definitions.keys():
                    if f"{api_name}(" in code_block:
                        usage_examples.append(APIUsageExample(
                            api_name=api_name,
                            code_snippet=code_block,
                            file_path=file_path,
                            line_number=line_number
                        ))
                        
        return usage_examples

    async def validate_usage_example(self, example: APIUsageExample) -> List[str]:
        """Use Claude to validate if an API usage example is correct.
        
        Sends the API definition and usage example to Claude for analysis
        of parameter usage, types, and other potential issues.
        
        Args:
            example (APIUsageExample): The example to validate
            
        Returns:
            List[str]: List of issues found, or ["No issues found"] if valid
        """
        api_def = self.api_definitions[example.api_name]
        
        prompt = f"""Please analyze this API usage example and verify if it matches the API definition.

API Definition:
- Name: {api_def.name}
- Parameters: {', '.join(api_def.params)}
- Return type: {api_def.return_type}
- Docstring: {api_def.docstring}

Usage Example:
```python
{example.code_snippet}
```

Please identify any mismatches in:
1. Parameter names and order
2. Parameter types (if type hints are present)
3. Return value usage
4. Any other potential issues

Respond with only a list of issues found, or "No issues found" if the usage is correct."""

        response = await self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return [issue.strip() for issue in response.content.split('\n') if issue.strip()]

    async def validate_all(self) -> Dict[str, List[str]]:
        """Validate all API usage examples found in documentation.
        
        Extracts API definitions from source code, finds all usage examples
        in documentation, and validates each example.
        
        Returns:
            Dict[str, List[str]]: Dictionary mapping file locations to lists of issues.
            Empty dict if no issues found.
        """
        self.extract_api_definitions()
        usage_examples = self.find_api_usage_examples()
        
        validation_results = {}
        for example in usage_examples:
            issues = await self.validate_usage_example(example)
            if issues and issues != ["No issues found"]:
                validation_results[f"{example.file_path}:{example.line_number}"] = issues
                
        return validation_results

    async def validate(self, api_docs: Dict[str, str]) -> ValidationResult:
        """Validate documentation against source code.
        
        Uses Claude to perform a comprehensive validation of API documentation
        against the source code implementation.
        
        Args:
            api_docs (Dict[str, str]): Dictionary containing:
                - 'source_code': The API source code
                - 'documentation': The documentation to validate
                
        Returns:
            ValidationResult: Result of the validation including any errors
                and improvement suggestions
                
        Raises:
            Exception: If validation fails due to API errors or other issues
        """
        try:
            # Construct the validation prompt
            prompt = self._build_validation_prompt(api_docs)
            
            # Get validation response from Claude
            response = await self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=4096,
                temperature=0,
                system="You are a technical documentation validator. Your task is to verify the accuracy of API documentation against source code. Be thorough and precise in your analysis.",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse validation results
            validation_result = self._parse_validation_response(response.content)
            
            if not validation_result.is_valid:
                self.logger.warning("Validation failed with errors:")
                for error in validation_result.errors:
                    self.logger.warning(f"- {error}")

            return validation_result

        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"],
                suggestions=[]
            )

    def _build_validation_prompt(self, api_docs: Dict[str, str]) -> str:
        """Build the prompt for documentation validation.
        
        Args:
            api_docs (Dict[str, str]): Source code and documentation to validate
            
        Returns:
            str: Formatted prompt for Claude
        """
        return f"""Please validate the following API documentation against the source code:

Source Code:
```python
{api_docs['source_code']}
```

Documentation:
```markdown
{api_docs['documentation']}
```

Please:
1. Verify that all documented functions and parameters match the source code
2. Check that return types and descriptions are accurate
3. Validate that example code is correct
4. Identify any missing or outdated documentation

Respond with:
- VALID if documentation is accurate
- INVALID if there are errors, followed by a list of specific issues
- Include specific suggestions for improvements

Your response should be structured as:
VALID|INVALID
ERRORS:
- Error 1
- Error 2
SUGGESTIONS:
- Suggestion 1
- Suggestion 2"""

    def _parse_validation_response(self, content) -> ValidationResult:
        """Parse Claude's validation response."""
        try:
            # Handle different response formats
            if isinstance(content, list):
                # Handle Claude 3 format with list of content objects
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item["text"]
                        break
                else:
                    raise ValueError("No text content found in response")
            else:
                text = str(content)
            
            lines = text.split('\n')
            status = lines[0]
            
            errors = []
            suggestions = []
            
            current_section = None
            for line in lines[1:]:
                if line.startswith('ERRORS:'):
                    current_section = 'errors'
                elif line.startswith('SUGGESTIONS:'):
                    current_section = 'suggestions'
                elif line.startswith('- '):
                    if current_section == 'errors':
                        errors.append(line[2:])
                    elif current_section == 'suggestions':
                        suggestions.append(line[2:])
                    
            return ValidationResult(
                is_valid=(status == 'VALID'),
                errors=errors,
                suggestions=suggestions
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse validation response: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Failed to parse validation response: {str(e)}"],
                suggestions=[]
            )
