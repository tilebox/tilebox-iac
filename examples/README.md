# Quickstarts and existing-infrastructure examples

The `quickstart` roots call the high-level AWS and GCP modules. They create the networking and secret resources required
to run a Tilebox runner cluster in an existing cloud account or project. These stacks can run production Tilebox
workloads. They do not configure other account- or project-wide networking, security, or organization controls.

The `existing-infrastructure` roots call the low-level modules with existing projects, networks, subnets, identities,
and secret references. They do not manage those resources.

CREODIAS uses separate `cluster` and `runner` roots because the Kubernetes provider must target a cluster that already
exists. Apply cluster then runner; destroy runner then cluster.
