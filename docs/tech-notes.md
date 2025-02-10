# Tech Notes

This document contains notes on various topics related to the LLM-Augmented Documentation CI/CD Pipeline project, including prompts, thoughts, observations, and other information outside the scope of a formal architecture document.

## Generating code and copy

Claude is very good at generating code and copy. It is also good at validating code and copy (This very sentence was written by Claude).

### Pipeline code

I have been using Cursor, an IDE that uses LLMs to generate and debug code, as my primary development environment. I have my engine set to use the Claude 3.5 Sonnet model.

Although the vast majority of the copy written was written by me, I did use Claude to help me write the code that validates code and builds the docs files.

### Example code for docs

We could leverage LLMs to generate code in the API reference step. Let's do this. We can also use LLMs to generate unit tests for the example code, and then generate test reports and use those reports to validate the example code.

## SDK release monitoring

We can set up a job that runs every hour to check the Anthropic Developer Portal for new SDK releases. If a new release is detected, the job can trigger a pipeline that builds the SDK and runs the validation pipeline on the new version.

Ideally, there is a way to trigger the pipeline from the actual release of the SDK, but that is outside the scope of this project.

## SDKs and third-party API reference generation

The pipeline explicitly uses Sphinx to generate the API reference documentation for Python SDKs. We can abstract this further to support other languages and documentation generation tools, but that is outside the scope of an MVP.
