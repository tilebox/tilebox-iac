# Pulumi examples

Copy an example directory into your own project. Install Python, uv, and the open-source Pulumi CLI, then run:

```bash
uv init --bare
uv add git+https://github.com/tilebox/tilebox-iac.git
pulumi login --local
pulumi stack init dev
```

State stays on your machine. Set the provider configuration below, then run `pulumi up` to preview and deploy.
Use `pulumi destroy` to remove a stack's resources when finished.

## AWS

Use [`aws/quickstart`](aws/quickstart) with your AWS credentials:

```bash
pulumi config set aws:region us-west-2
pulumi config set --secret tileboxApiKey
```

[`aws/existing-infrastructure`](aws/existing-infrastructure) instead takes `subnetIds` and `securityGroupIds` as JSON
arrays, plus `apiKeySecretArn`. Optional `roleName` and `instanceProfileName` reuse an existing identity; pass both.

```bash
pulumi config set --path 'subnetIds[0]' subnet-0123456789abcdef0
pulumi config set --path 'securityGroupIds[0]' sg-0123456789abcdef0
pulumi config set apiKeySecretArn arn:aws:secretsmanager:us-west-2:123456789012:secret:tilebox-AbCdEf
```

## GCP

Use [`gcp/quickstart`](gcp/quickstart) after `gcloud auth application-default login`:

```bash
pulumi config set gcp:project YOUR_PROJECT_ID
pulumi config set --secret tileboxApiKey
```

[`gcp/existing-infrastructure`](gcp/existing-infrastructure) instead takes `networkId`, `subnetId`, and `apiKeySecretId`
(`projects/PROJECT/secrets/SECRET`). Optional `serviceAccountEmail` reuses an identity. For Shared VPC, set
`hostProject` to the project owning the network. See the [GCP guide](../tilebox_iac/gcp/README.md) for permissions and healing.

Both existing-infrastructure examples accept `secretRevision` to roll workers after an external secret changes.

## Azure

The [Azure guide](../tilebox_iac/azure/README.md) includes a complete program for runners, Key Vault, and independent
Blob Storage, with local-state setup and scale-set update commands.

## CREODIAS and Kubernetes

Follow the [CREODIAS example](creodias/README.md). Deploy the cluster first, then its runners in a separate stack.
