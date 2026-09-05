# Server Dashboard

## Automatic service discovery

Cards are discovered from Docker container labels at runtime. There is no service
inventory in the application or tracked Compose configuration. Only containers
with the exact label `dashboard.enable=true` are returned. The running count also
includes only enabled containers. No container IDs, images, ports, environment
values or unrelated labels are returned.

Optional labels: `dashboard.name` (default `Service`), `dashboard.description`,
`dashboard.tag`, `dashboard.url`, `dashboard.order` (integer, default 100).
Cards sort by order, name, then URL. URLs accept HTTP(S) or local paths starting
with `/`; missing or unsafe URLs produce a card without a link. Label text is
rendered as text, not HTML.

Stopped enabled containers remain visible with their status. Removed or disabled
containers disappear at the next five-second refresh. Docker failures clear stale
cards and show an unavailable message.

## Private service configuration

Keep actual card names and URLs on the server, outside Git. In each service's
Compose directory, put labels in a private `compose.override.yaml`, using the
service key from that project's base Compose file. For example:

```yaml
services:
  example-service:
    labels:
      dashboard.enable: "true"
      dashboard.name: "Example Service"
      dashboard.description: "An example application."
      dashboard.url: "https://app.example.com/"
      dashboard.tag: "Tools"
      dashboard.order: "10"
```

This repository ignores `compose.override.yaml` and `docs/local-services.md`
(local migration notes). Add the same ignore rule to any other service repository
before creating its private override. Never force-add private configuration.

Docker Compose loads `compose.override.yaml` alongside the default base file.
When using explicit `-f` options, include both the base and override files.
The dashboard reads the resulting container labels through the Docker API; it
 does not read YAML files or scan a directory itself.

Changing labels requires recreating the affected container. To hide a service,
remove the enable label or set it to `"false"`, then recreate it. Adding or
changing services requires no dashboard code changes.

Before a future rollout, label existing services first, then update the API and
page together. Unlabelled services intentionally have no fallback cards. Current
changes are local only and have not been deployed. Changes to current files do
not remove information from earlier Git commits.

## Local tests

With Python requirements installed and Node.js available:

```text
python -m unittest discover -s tests -v
node --test tests/services.test.cjs
```

Tests use fictional services, mocked Docker and host metrics, and execute the
page's actual script against a minimal DOM. They do not contact a Docker daemon
or server.
