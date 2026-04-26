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

## Entity And Device References

CI checks that referenced Home Assistant entities and `device_id` values are either defined in this repo or listed in:

- `.ci/known_entities.txt`
- `.ci/known_devices.txt`

When adding a real Home Assistant entity or device, update the baseline:

```sh
npm run update:ha-refs
```

Generated/runtime files such as `.storage/`, databases, private keys, `.DS_Store`, and `__pycache__` must not be committed.

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
