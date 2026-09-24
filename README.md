# Home Assistant Bhavya

Home Assistant configuration with CI checks for config validity, formatting, secrets, and stale entity/device references.

## Branches

- `develop` is the working branch.
- `main` is the stable branch and should be protected in GitHub.

## Local Checks

Run the same core checks before opening a PR:

```sh
npm run format:check
npm run check:ha-refs
.venv/bin/yamllint -c .yamllint .
.venv/bin/pre-commit run --all-files
```

## Automations

Automations are loaded from `src/automations/` with `!include_dir_merge_list`.
Add new automations to the closest area file, or use a cross-cutting file such as
`system.yaml`, `energy.yaml`, `heating.yaml`, `media.yaml`, or `vacuum.yaml`.

## Entity And Device References

CI checks that referenced Home Assistant entities and `device_id` values are either defined in this repo or listed in:

- `.ci/known_entities.txt`
- `.ci/known_devices.txt`

When adding a real Home Assistant entity or device, update the baseline:

```sh
npm run update:ha-refs
```

Generated/runtime files such as `.storage/`, databases, private keys, `.DS_Store`, and `__pycache__` must not be committed.

## Live Home Assistant Inspection

For work that needs the running Home Assistant device registry, entity registry, exposed entities, or live states, use:

```sh
HA_URL=http://homeassistant.local:8123 HA_TOKEN=... npm run ha:live
```

`HA_TOKEN` should be a Home Assistant long-lived access token from your Home Assistant profile page. The script reads:

- REST API: `/api/`, `/api/config`, `/api/states`, `/api/services`
- WebSocket API: entity registry, device registry, area registry, labels, and exposed entities

The snapshot is written to `artifacts/ha-live-snapshot.json`, which is ignored by git. Do not commit tokens or live snapshots.

## Deploying Home Assistant

Home Assistant can deploy either branch from `/config`:

- `main` = prod
- `develop` = preprod/testing

Available HA scripts:

- `script.deploy_home_assistant_main`
- `script.deploy_home_assistant_develop`
- `script.deploy_home_assistant_selected_branch`

There is also a nightly Home Assistant automation that deploys `main` at `00:00` local time.

GitHub Actions also includes a manual `HA deploy` workflow for remote branch switching. The workflow requires these repository secrets:

- `HA_SSH_HOST`
- `HA_SSH_PORT`
- `HA_SSH_USER`
- `HA_SSH_KEY`
