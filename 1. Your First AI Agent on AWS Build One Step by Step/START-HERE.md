# Veriqta AWS AI Agent

Build a read-only cloud operations assistant with Python, Amazon Bedrock, Lambda, and API Gateway.

Read **AWS-AI-Agent-Complete-Notes.md** for the full handbook.

## Project files

- `code/aws_agent/`: configuration, AWS tools, agent loop, memory, API handler, and CLI.
- `code/tests/`: automated tests and an opt-in AWS integration check.
- `code/web/`: browser interface with Cognito PKCE login.
- `infra/`: deployment template and development policy template.
- `scripts/`: Lambda packaging and browser configuration.
- `notes/`: test event and deployment verification worksheet.

## Run tests

From the project root with Python 3.12 installed:

```bash
python3 -m unittest discover -s code/tests -v
```

Configure the AWS identity, region, model, and permissions before running the live examples. Follow the deployment and cleanup chapters when provisioning resources.
