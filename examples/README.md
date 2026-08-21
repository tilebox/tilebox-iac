# Quickstarts and advanced examples

The `quickstart` roots are the primary onboarding path. They are thin wrappers around the high-level AWS and GCP
modules, which create only enough networking and secret infrastructure to run a Tilebox runner cluster in an existing
cloud account or project. These stacks can run production Tilebox workloads, but they intentionally do not configure
broader account- or project-wide networking, security, or organization controls.

The `existing-infrastructure` roots are the advanced integration path. They consume customer-owned projects, networks,
subnets, workload identities, and secret references without taking ownership of the surrounding environment.

CREODIAS uses separate `cluster` and `runner` roots because the Kubernetes provider must target a cluster that already
exists. Apply cluster then runner; destroy runner then cluster.
