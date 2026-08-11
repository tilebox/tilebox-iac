# Examples

The `existing-infrastructure` examples are the primary integration path. They consume customer-owned projects,
networks, subnets, workload identities, and secret references without taking ownership of the surrounding environment.

The optional `greenfield` examples create only enough disposable infrastructure to evaluate a module. They are not
reusable landing-zone modules and are not production architecture recommendations.

CREODIAS uses separate `cluster` and `runner` roots because the Kubernetes provider must target a cluster that already
exists. Apply cluster then runner; destroy runner then cluster.
