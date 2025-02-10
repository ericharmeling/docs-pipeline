import sys
from pathlib import Path
import subprocess
from dataclasses import dataclass
import logging
from utils.example_generator import ExampleGenerator
from typing import Optional, List, Dict
import ast
from utils.types import APIMethod, SphinxConfig, CodeExample

class APIDocGenerator:
    """Generates API documentation using Sphinx.
    
    This class handles the complete workflow of generating API documentation,
    from discovering API methods to building the final HTML output.
    
    Example:
        ```python
        config = SphinxConfig(
            project_name="MySDK",
            author="Development Team",
            version="1.0.0",
            source_dir=Path("./src"),
            docs_dir=Path("./docs"),
            output_dir=Path("./docs/html")
        )
        
        generator = APIDocGenerator(config, api_key="your-api-key")
        await generator.generate()
        ```
    """
    
    def __init__(self, config: SphinxConfig, api_key: str):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.example_generator = ExampleGenerator(api_key)

    async def discover_api_methods(self, files: Optional[List[Path]] = None) -> List[APIMethod]:
        """Discover API methods from source code.
        
        Args:
            files: Optional list of files to scan. If None, scans all files.
        """
        api_methods = []
        
        if files is None:
            # Only look in source directory
            files = list(self.config.source_dir.rglob("*.py"))
        else:
            # Filter out test files and sphinx config files
            files = [
                f for f in files 
                if "tests" not in f.parts 
                and "docs" not in f.parts
                and f.is_file()
            ]
        
        for py_file in files:
            try:
                # Add path validation
                if not self._validate_path(py_file, self.config.source_dir):
                    self.logger.error(f"'{py_file}' is not in the subpath of '{self.config.source_dir}'")
                    continue
                    
                methods = self.parse_module_for_methods(py_file)
                api_methods.extend(methods)
            except Exception as e:
                self.logger.error(f"Failed to parse {py_file}: {e}")
                
        return api_methods

    async def generate_examples(self, api_methods: List[APIMethod]) -> Dict[str, List[CodeExample]]:
        """Generate examples for discovered API methods.
        
        Args:
            api_methods: List of API methods to generate examples for
            
        Returns:
            Dict[str, List[CodeExample]]: Dictionary mapping method names to their examples
        """
        examples_by_method = {}
        for method in api_methods:
            examples = await self.example_generator.generate_examples(method)
            examples_by_method[method.name] = examples
        return examples_by_method

    async def generate_docs(self, api_methods: List[APIMethod], 
                          examples_by_method: Dict[str, List[CodeExample]]) -> Dict[str, str]:
        """Generate documentation using discovered methods and examples.
        
        Args:
            api_methods: List of API methods to document
            examples_by_method: Dictionary of examples for each method
            
        Returns:
            Dict[str, str]: Generated documentation content
        """
        # Generate RST content for each method with its examples
        for method in api_methods:
            examples = examples_by_method.get(method.name, [])
            await self.generate_api_rst(method, examples)
        
        # Return complete documentation
        return {
            'source_code': self._get_source_content(),
            'documentation': self._get_docs_content()
        }

    def setup_sphinx_dirs(self) -> None:
        """Create necessary directories for Sphinx documentation.
        
        Creates the following directory structure if it doesn't exist:
        - docs_dir/
            - source/
            - build/
        """
        # Create docs directory if it doesn't exist
        self.config.docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create source directory for RST files
        source_dir = self.config.docs_dir / "source"
        source_dir.mkdir(exist_ok=True)
        
        # Create build directory
        build_dir = self.config.docs_dir / "build"
        build_dir.mkdir(exist_ok=True)

    def generate_conf_py(self) -> None:
        """Generate Sphinx configuration file.
        
        Creates a conf.py file in the source directory with settings for:
        - Project information (name, author, version)
        - Extensions (autodoc, napoleon, etc.)
        - Theme configuration
        - Napoleon settings for docstring parsing
        - Intersphinx mappings
        """
        conf_py_content = f'''
import os
import sys
sys.path.insert(0, os.path.abspath('{self.config.source_dir}'))

project = '{self.config.project_name}'
copyright = '2024, {self.config.author}'
author = '{self.config.author}'
version = '{self.config.version}'
release = version

extensions = {self.config.extensions}

templates_path = ['_templates']
exclude_patterns = []

html_theme = '{self.config.theme}'
html_static_path = ['_static']

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_type_aliases = None

# Intersphinx settings
intersphinx_mapping = {{
    'python': ('https://docs.python.org/3', None),
}}
'''
        
        conf_py_path = self.config.docs_dir / "source" / "conf.py"
        conf_py_path.write_text(conf_py_content)

    def generate_index_rst(self) -> None:
        """Generate main index.rst file.
        
        Creates the root documentation file that:
        - Displays the project welcome message
        - Sets up the documentation structure
        - Includes the API documentation
        - Adds standard Sphinx indices
        """
        index_content = f'''
Welcome to {self.config.project_name}'s documentation!
{'=' * (len(self.config.project_name) + 28)}

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
   
Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
'''
        
        index_path = self.config.docs_dir / "source" / "index.rst"
        index_path.write_text(index_content)

    async def generate_api_examples(self, api_method: APIMethod) -> str:
        """Generate examples for an API method.
        
        Uses the ExampleGenerator to create code examples demonstrating
        the usage of the given API method.
        
        Args:
            api_method (APIMethod): Method to generate examples for
            
        Returns:
            str: Formatted examples in Sphinx RST format
        """
        examples = await self.example_generator.generate_examples(api_method)
        return self.example_generator.format_for_sphinx(examples)

    async def generate_api_rst(self, api_method: APIMethod, examples: List[CodeExample]) -> None:
        """Generate API documentation RST file for a single method.
        
        Creates an RST file containing:
        - Auto-generated documentation from docstrings
        - Generated code examples
        - Cross-references between API methods
        
        The generated file follows the Sphinx autosummary format.
        """
        api_content = f'''
API Documentation
================

.. autosummary::
   :toctree: _autosummary
   :recursive:

{api_method.name}

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
   
Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Examples
--------

{self.example_generator.format_for_sphinx(examples)}
'''
        
        output_path = self.config.docs_dir / "source" / f"{api_method.name}.rst"
        output_path.write_text(api_content)

    def install_dependencies(self) -> None:
        """Install required Sphinx packages.
        
        Installs the following packages using pip:
        - sphinx
        - sphinx-rtd-theme
        - sphinx-autodoc-typehints
        
        Raises:
            subprocess.CalledProcessError: If package installation fails
        """
        requirements = [
            "sphinx",
            "sphinx-rtd-theme",
            "sphinx-autodoc-typehints",
        ]
        
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", *requirements],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to install dependencies: {e.stderr.decode()}")
            raise

    def build_docs(self) -> None:
        """Build Sphinx documentation.
        
        Runs sphinx-build to generate HTML documentation from the
        RST files in the source directory.
        
        Raises:
            subprocess.CalledProcessError: If documentation build fails
        """
        try:
            subprocess.run(
                ["sphinx-build", "-b", "html", 
                 str(self.config.docs_dir / "source"),
                 str(self.config.output_dir)],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to build documentation: {e.stderr.decode()}")
            raise

    async def generate(self) -> None:
        """Generate complete API documentation.
        
        This method orchestrates the entire documentation generation process:
        1. Sets up Sphinx directories
        2. Installs required dependencies
        3. Generates configuration files
        4. Discovers and documents API methods
        5. Builds final HTML documentation
        
        Raises:
            Exception: If any step of the documentation generation fails
        """
        try:
            self.logger.info("Setting up Sphinx directories...")
            self.setup_sphinx_dirs()
            
            self.logger.info("Installing dependencies...")
            self.install_dependencies()
            
            self.logger.info("Generating Sphinx configuration...")
            self.generate_conf_py()
            
            self.logger.info("Generating index.rst...")
            self.generate_index_rst()
            
            self.logger.info("Generating API documentation RST files...")
            api_methods = await self.discover_api_methods()
            examples_by_method = await self.generate_examples(api_methods)
            await self.generate_docs(api_methods, examples_by_method)
            
            self.logger.info("Building documentation...")
            self.build_docs()
            
            self.logger.info(f"Documentation successfully generated at {self.config.output_dir}")
            
        except Exception as e:
            self.logger.error(f"Documentation generation failed: {str(e)}")
            raise

    def parse_module_for_methods(self, path: Path) -> list[APIMethod]:
        """Parse a Python module file to find API methods.
        
        Analyzes a Python source file using the ast module to discover public methods
        that should be included in the API documentation.
        
        Args:
            path (Path): Path to the Python module file to parse
            
        Returns:
            list[APIMethod]: List of API methods found in the module
            
        Example:
            ```python
            methods = generator.parse_module_for_methods(Path("sdk/client.py"))
            for method in methods:
                print(f"Found {method.name} with signature: {method.signature}")
            ```
        """
        methods = []
        module_text = path.read_text()
        module_ast = ast.parse(module_text)
        module_name = str(path.relative_to(self.config.source_dir)).replace('/', '.').replace('.py', '')

        for node in ast.walk(module_ast):
            if isinstance(node, ast.FunctionDef):
                # Skip private methods
                if node.name.startswith('_'):
                    continue
                    
                docstring = ast.get_docstring(node)
                signature = self._get_function_signature(node)
                
                method = APIMethod(
                    name=node.name,
                    module=module_name,
                    docstring=docstring,
                    signature=signature,
                    path=path
                )
                methods.append(method)
                
        return methods

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature as string.
        
        Args:
            node (ast.FunctionDef): AST node representing a function definition
            
        Returns:
            str: Function signature in the format "name(arg1, arg2, ...)"
        """
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        return f"{node.name}({', '.join(args)})"

    def _get_source_content(self) -> str:
        """Get source code content as a string.
        
        Returns:
            str: Source code content
        """
        source_content = ""
        for path in self.config.source_dir.rglob("*.py"):
            if path.name != "__init__.py":
                source_content += path.read_text() + "\n"
        return source_content

    def _get_docs_content(self) -> str:
        """Get documentation content as a string.
        
        Returns:
            str: Documentation content
        """
        docs_content = ""
        for path in self.config.docs_dir.rglob("*.rst"):
            docs_content += path.read_text() + "\n"
        return docs_content

    def _validate_path(self, file_path: Path, base_dir: Path) -> bool:
        """Validate that file_path is within base_dir."""
        try:
            # Convert both to absolute paths and resolve any symlinks
            file_abs = file_path.resolve()
            base_abs = base_dir.resolve()
            return str(file_abs).startswith(str(base_abs))
        except Exception as e:
            self.logger.error(f"Path validation failed: {e}")
            return False

    async def build_html(self):
        """Build HTML documentation from RST files using Sphinx."""
        try:
            # Install required packages first
            self.install_dependencies()
            
            # Setup required directories and files
            self.setup_sphinx_dirs()
            self.generate_conf_py()
            self.generate_index_rst()
            
            # Build HTML using existing method
            self.build_docs()
            
        except Exception as e:
            self.logger.error(f"Failed to build HTML documentation: {e}")
            raise
