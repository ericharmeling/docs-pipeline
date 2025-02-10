# LLM-Augmented Documentation CI/CD Pipeline

*A build pipeline that generates, validates, and publishes developer documentation for development SDKs.*

**Note:** This project is in-development and not yet ready for use in a production environment.

## Overview

This project defines and documents a CI/CD developer documentation pipeline for development SDKs. This pipeline is designed to ensure that both dynamic and static documentation and code samples maintain technical accuracy. The pipeline also generates documentation from source code, using LLM APIs and API reference generation tools.

This project is specifically tailored to Anthropic's Claude SDK for Python, but the pipeline and approach are generalizable to other developer ecosystems.

For more details on the pipeline design and implementation, see the [architecture document](docs/architecture.md).

## Motivation

Documentation is only useful if it is trusted by the developers who use it. Technical accuracy is the easiest way to build trust with a developer base, and technical inaccuracies are the easiest way to lose trust. It is critical that the documentation is always accurate and up-to-date.

Manually authored developer documentation, especially documentation that includes sample code and references to specific APIs, decay rapidly and require constant maintenance. 

To more efficiently maintain developer documentation, I propose an LLM-augmented CI/CD pipeline that automatically validates the technical accuracy of the documentation, using the source code of the SDK as the primary source of truth. We can also leverage LLMs to generate example code and corresponding unit tests from the source code, which can be used to supplement manually authored documentation.

## Running the pipeline

The pipeline is designed to be run in a CI/CD environment, specifically using GitHub Actions and GitHub Pages, but it can also be run locally.

### Local build

To run the pipeline locally, you need the following:

- An Anthropic Claude API key
- Docker
- Docker daemon running

With the API key set to the `ANTHROPIC_API_KEY` environment variable, run the pipeline locally using the following command:

```bash
./runlocal.sh
```

### Local integration test

In order to run the pipeline build integration test, you need to have the following:

- Docker
- Docker daemon running
- Python 3.11

To run the pipeline build integration test, you can run the following command:

```bash
./tests/integration/test_build.py
```

