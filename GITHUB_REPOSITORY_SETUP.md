# Create the GitHub repository

Target repository: `OasisSaber/IdlerDream`

Recommended initial visibility: **private**. The project contains security-sensitive local-inspection code and has not completed its Windows release review.

## Automated path with GitHub CLI

From the extracted `IdlerDream` directory in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\create-github-repo.ps1
```

The script:

1. verifies `git` and `gh`;
2. checks GitHub authentication;
3. initializes a `main` branch when necessary;
4. commits the reviewed baseline;
5. creates `OasisSaber/IdlerDream` as a private repository;
6. pushes `main`.

It stops rather than overwrite an existing remote or repository.

## Manual GitHub UI path

1. Open GitHub and create a new repository named `IdlerDream` under `OasisSaber`.
2. Select **Private**.
3. Do not initialize README, `.gitignore` or license; these files already exist.
4. Run:

```powershell
git init -b main
git add -- .editorconfig .gitignore .github AGENTS.md ASSET_INDEX.md GITHUB_REPOSITORY_SETUP.md README.md apps design-system docs examples package.json packages preview prompts pyproject.toml resources scripts
git commit -m "chore: bootstrap IdlerDream reviewed baseline"
git remote add origin https://github.com/OasisSaber/IdlerDream.git
git push -u origin main
```

## Repository metadata

Description:

> Local-first Windows dashboard for monitoring project workspaces and coding Agent processes, with constrained OpenCode status inspection.

Topics:

```text
agent-dashboard local-first electron react python opencode developer-tools windows
```

## After first push

- Keep the repository private until the threat model and installer are validated.
- Enable secret scanning and Dependabot alerts where available.
- Protect `main`: require pull requests and successful CI.
- Create issues from the open findings in `docs/CODE_REVIEW.md`.
- Do not add an open-source license until the intended license is selected.
