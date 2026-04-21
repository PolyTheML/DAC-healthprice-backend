# AWS & Cloud Infrastructure

**Type**: Entity / Cloud Platform

---

## Overview

Amazon Web Services (AWS) provides the cloud infrastructure and managed services used in modern insurance underwriting applications.

## Services for Underwriting Workbench

### AI/ML Services
- **Amazon Bedrock**: Managed LLM service for [Claude](./claude.md) deployment
- Serverless, no infrastructure management needed
- Per-token pricing, scales with demand

### Compute
- **AWS Lambda**: Serverless functions for document processing, extraction, scoring
- Scales automatically with volume
- Pay only for computation time

### Orchestration
- **AWS Step Functions**: Workflow engine
- Orchestrates multi-step processes (extract → score → route → log)
- Handles error handling and retries

### Storage
- **Amazon S3**: Document storage (PDFs, images, extracted data)
- **DynamoDB**: Metadata and decision logs
- Both scalable and cost-effective

### Frontend
- **AWS API Gateway** + **React with Vite**: Web interface for underwriters
- Deployed via **AWS Amplify** or **CloudFront**

## Architecture Benefits

### Scalability
- Auto-scales with underwriting volume
- No capacity planning needed
- Pay-per-use model

### Security
- Encryption at rest and in transit
- IAM roles for access control
- Audit logging built-in

### Cost Efficiency
- Managed services reduce operational overhead
- No dedicated server maintenance
- Batch processing cheaper than real-time

## Reference Implementation

See: [AWS GenAI Underwriting Workbench](../sources/aws-genai-underwriting-workbench.md)

Provides an end-to-end, production-grade example of:
- Serverless architecture
- Lambda + Step Functions workflow
- Bedrock LLM integration
- DynamoDB logging for compliance

## Infrastructure as Code

The workbench uses **AWS CDK** (Cloud Development Kit):
- Define infrastructure as code (Python/TypeScript)
- Reproducible deployments
- Version control for infrastructure

## Related Topics

- [AWS GenAI Underwriting Workbench](../sources/aws-genai-underwriting-workbench.md)
- [Document Extraction & Medical Parsing](../topics/document-extraction.md)
