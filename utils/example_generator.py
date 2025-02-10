from typing import List
import anthropic
import logging
from pathlib import Path
from utils.types import APIMethod, CodeExample

class ExampleGenerator:
    """Generates code examples and tests for API methods using Claude.
    
    This class uses the Anthropic Claude API to generate:
    - Usage examples with realistic scenarios
    - Example outputs
    - Unit tests for the examples
    
    Example:
        ```python
        generator = ExampleGenerator(api_key="your-anthropic-api-key")
        examples = await generator.generate_examples(api_method)
        print(generator.format_for_sphinx(examples))
        ```
    """

    def __init__(self, api_key: str):
        self.client = anthropic.Client(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    async def generate_test(self, api_method: APIMethod, example: CodeExample) -> str:
        """Generate a unit test for a specific code example.
        
        Uses Claude to create a pytest-based unit test that validates
        the example code works as expected.
        
        Args:
            api_method (APIMethod): The API method being tested
            example (CodeExample): The example to generate a test for
            
        Returns:
            str: Generated pytest code, or None if generation fails
            
        Example:
            ```python
            test_code = await generator.generate_test(method, example)
            if test_code:
                print("Generated test:")
                print(test_code)
            ```
        """
        
        prompt = f"""Generate a pytest unit test for this API example:

        API Method: {api_method.name}
        Parameters: {api_method.parameters}
        Return Type: {api_method.return_type}

        Example Code:
        {example.code}

        Expected Output:
        {example.output}

        Requirements:
        1. Use pytest fixtures where appropriate
        2. Include mocking of external services/APIs
        3. Test both success and error cases
        4. Add assertions to verify the output
        5. Include docstring explaining the test
        6. Use pytest.mark decorators if needed
        7. Follow testing best practices

        Return only the test code without any additional explanation.
        """

        try:
            response = await self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0.5,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract test code from response
            test_code = response.content[0].text
            if "```python" in test_code:
                test_code = test_code.split("```python")[1].split("```")[0].strip()
            return test_code
            
        except Exception as e:
            self.logger.error(f"Failed to generate test for example: {e}")
            return None

    async def generate_examples(self, method: APIMethod) -> List[CodeExample]:
        """Generate code examples for an API method."""
        try:
            prompt = self._build_example_prompt(method)
            response = await self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=4096,
                temperature=0,
                system="You are a technical documentation assistant. Generate clear, practical code examples that demonstrate proper API usage. Include test cases that verify the functionality.",
                messages=[{
                    "role": "user", 
                    "content": f"""Please generate example code and tests for this API method:

Method Name: {method.name}
Docstring: {method.docstring}
Parameters: {method.parameters}
Return Type: {method.return_type}

For each example, provide:
1. A description of what the example demonstrates
2. The example code itself
3. A pytest test case that verifies the example works

Format each example as:
EXAMPLE:
<description>
CODE:
<example code>
TEST:
<test code>

Generate 2-3 examples that show different use cases."""
                }]
            )
            
            # Handle Claude response format - response.content is a list of dictionaries
            if response.content:
                # Get the text content from the first message
                return self._parse_examples(response.content[0]["text"], method)
            
            raise ValueError("No content found in response")
            
        except Exception as e:
            self.logger.error(f"Failed to generate examples for {method.name}: {e}")
            return []

    def _parse_examples(self, content: str, method: APIMethod) -> List[CodeExample]:
        """Parse examples from Claude's response."""
        examples = []
        current_example = None
        current_section = None
        
        for line in content.split('\n'):
            if line.startswith('EXAMPLE:'):
                if current_example:
                    examples.append(current_example)
                current_example = CodeExample(description="", code="", test_code=None)
                current_section = 'description'
            elif line.startswith('CODE:'):
                current_section = 'code'
            elif line.startswith('TEST:'):
                current_section = 'test'
            elif current_example and line.strip():
                if current_section == 'description':
                    current_example.description += line + '\n'
                elif current_section == 'code':
                    current_example.code += line + '\n'
                elif current_section == 'test':
                    if current_example.test_code is None:
                        current_example.test_code = ''
                    current_example.test_code += line + '\n'
                
        if current_example:
            examples.append(current_example)
        
        return examples

    def format_for_sphinx(self, examples: List[CodeExample]) -> str:
        """Format code examples for Sphinx documentation.
        
        Converts the examples into RST format with proper code block
        formatting and indentation.
        
        Args:
            examples (List[CodeExample]): Examples to format
            
        Returns:
            str: RST-formatted example documentation
            
        Example:
            ```python
            rst_content = generator.format_for_sphinx(examples)
            with open('api_examples.rst', 'w') as f:
                f.write(rst_content)
            ```
        """
        result = []
        
        for i, example in enumerate(examples, 1):
            result.append(f"Example {i}: {example.description}\n")
            result.append(".. code-block:: python\n")
            
            # Indent code for Sphinx code block
            code_lines = ["    " + line for line in example.code.split("\n")]
            result.append("\n".join(code_lines))
            
            result.append("\nOutput:\n")
            result.append(".. code-block:: none\n")
            
            # Indent output for Sphinx code block
            output_lines = ["    " + line for line in example.output.split("\n")]
            result.append("\n".join(output_lines))
            
            if example.test_code:
                result.append("\nUnit Test:\n")
                result.append(".. code-block:: python\n")
                
                # Indent test code for Sphinx code block
                test_lines = ["    " + line for line in example.test_code.split("\n")]
                result.append("\n".join(test_lines))
            
            result.append("\n")
            
        return "\n".join(result)

    async def generate_test_file(self, api_method: APIMethod, examples: List[CodeExample]) -> str:
        """Generate a complete test file for all examples of an API method."""
        
        test_file = f"""import pytest
from unittest.mock import Mock, patch
from your_package import {api_method.name}

# Generated test file for {api_method.name}
"""
        
        # Add all example tests
        for example in examples:
            if example.test_code:
                test_file += f"\n{example.test_code}\n"
        
        return test_file 

    async def save_test_files(self, base_test_dir: str, api_method: APIMethod, examples: List[CodeExample]):
        """Save generated tests to the test directory."""
        
        # Create test directory if it doesn't exist
        test_dir = Path(base_test_dir)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate and save test file
        test_file_path = test_dir / f"test_{api_method.name.lower()}.py"
        test_content = await self.generate_test_file(api_method, examples)
        
        with open(test_file_path, "w") as f:
            f.write(test_content)
            
        self.logger.info(f"Generated test file: {test_file_path}") 

    async def validate_generated_tests(self, test_file_path: str) -> bool:
        """Run pytest on the generated test file to validate it."""
        import pytest
        
        try:
            # Run pytest programmatically
            exit_code = pytest.main([
                test_file_path,
                "-v",
                "--disable-warnings"
            ])
            
            if exit_code == 0:
                self.logger.info(f"Tests in {test_file_path} passed successfully")
                return True
            else:
                self.logger.error(f"Tests in {test_file_path} failed with exit code {exit_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error validating tests in {test_file_path}: {e}")
            return False 

    def _build_example_prompt(self, method: APIMethod) -> str:
        """Build prompt for generating examples."""
        return f"""Please generate example code and tests for this API method:

Method Name: {method.name}
Docstring: {method.docstring}
Parameters: {method.parameters}
Return Type: {method.return_type}

For each example, provide:
1. A description of what the example demonstrates
2. The example code itself
3. A pytest test case that verifies the example works

Format each example as:
EXAMPLE:
<description>
CODE:
<example code>
TEST:
<test code>

Generate 2-3 examples that show different use cases.""" 