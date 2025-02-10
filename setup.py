from setuptools import setup, find_packages

setup(
    name="api-doc-generator",
    version="1.0.0",
    description="API Documentation Generator using Claude",
    author="Anthropic",
    packages=find_packages(),
    install_requires=[
        "anthropic",
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "sphinx",
        "coverage",
        "aiohttp",
        "pyyaml",
        "gitpython",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "generate-docs=build.build:main",
            "monitor-versions=utils.version_monitor:main",
        ],
    },
) 