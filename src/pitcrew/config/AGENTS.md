# config/

What the service is configured with.

| Module | Holds |
|--------|-------|
| `settings.py` | `Settings`: the service env, read with `pydantic-settings` |
| `team.py` | `TeamConfig` / `TeamConfigs`: the Team configs, YAML in the root `config/`; `TeamConfigs.get` raises `UnknownTeamException` for a Team without one; `team_config_file`, the file a Team's config lives in. `RerunConfig.pipeline_inputs` takes the GitLab client's `InputValue` |

## Settings

- Read from the environment, then `src/service.env`; never from the root `.env`, which belongs
  to the development agent.
- `Settings` holds the service's own values and a group per concern, each reading its variables
  by their prefix: `allure` (`ALLURE_*`), `gitlab` (`GITLAB_*`), `litellm` (`LITELLM_*`), `agent`
  (`AGENT_*`). A new external service gets its own `<Name>Settings(_EnvSettings)` with its
  `env_prefix` and a field in `Settings`; its client takes only that group.
- A secret is a `SecretStr` field: `_EnvSettings` registers it for masking as it is read. A
  secret a Team config names by its variable is read with `Settings.secret`, masked the same way.
- A new variable gets one commented line in `src/service.env.example`.
- `LogSettings` stays apart from `Settings`: logging is set up when the app is imported, before
  the rest of the config is validated.

## Team configs

- `base.yaml` with `<team lowercased>.yaml` deep-merged over it, validated at startup: an
  invalid config, or a Slack webhook variable it names that is not set, stops the startup.
- Every model is `extra="forbid"` and `frozen`: a misspelled key fails instead of being ignored.
- A rule across fields is a `model_validator` on the model that holds them.
- Team configs hold no secret: a secret lives in the environment and the config names its
  variable.
- A Team is any name with a Team config: a new Team is a new YAML file and no code change.
  No list of Teams is kept in the code; the trigger's Team is a string, checked only by
  `TeamConfigs.get`, which finds the config whatever the spelling.
- A Team config names its Team (`name`, as `qa_automation` spells its `PROJECT_NAME`, e.g.
  `Gateway`) and lives in `team_config_file(name)`, the name lowercased: a file named
  otherwise stops the startup. `team_config_file` is the one place of that rule; the lookup
  goes through it too.
- From the lookup on, the Team is `team_config.name`: the Run chain stores it and the Rerun's
  `PROJECT_NAME` and the Conclusion use it, never the trigger's spelling.
- A type of an external API a Team config holds (the GitLab pipeline's `InputValue`) is
  defined by its client and imported from there: a client imports nothing from `team.py`.

## Tests

`tests/test_config/`; Team config variants in `tests/data/team_configs/`.
