# IdlerDream GitHub repository setup prompt

You are preparing the reviewed IdlerDream asset directory as a new GitHub repository for `OasisSaber`.

## Required outcome

Create a private repository named `OasisSaber/IdlerDream`, make `main` the default branch, and publish the existing reviewed files as the initial commit.

## Mandatory preflight

1. Read `docs/CODE_REVIEW.md`, `AGENTS.md` and `.gitignore`.
2. Confirm the current directory is the IdlerDream root.
3. Confirm no API keys, `.env`, raw reports, user databases, build outputs or credential files are staged.
4. Check whether `OasisSaber/IdlerDream` already exists. Never overwrite or force-push an existing repository.
5. Show the exact staged file list before committing.

## Commit and publish

- Initialize Git with branch `main` only when `.git` is absent.
- Stage only the explicit repository assets; never use `git add -A`, `git add .` or `git add --all`.
- Initial commit message: `chore: bootstrap IdlerDream reviewed baseline`.
- Create the GitHub repository as private.
- Add the repository description and topics from `GITHUB_REPOSITORY_SETUP.md`.
- Push `main` without force.

## After publishing

1. Verify the remote tree and commit SHA.
2. Enable secret scanning/Dependabot alerts when supported.
3. Add main-branch protection requiring pull requests and CI when supported.
4. Create one issue per unresolved High-severity finding in `docs/CODE_REVIEW.md`, preserving the finding ID.
5. Do not create a release or publish binaries.
6. Report the repository URL, initial commit SHA, settings applied and any step that could not be completed.
