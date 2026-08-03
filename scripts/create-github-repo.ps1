$ErrorActionPreference = "Stop"

$Owner = "OasisSaber"
$Repo = "IdlerDream"
$FullName = "$Owner/$Repo"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git is not installed or not on PATH." }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) is not installed or not on PATH." }

gh auth status | Out-Host

if (-not (Test-Path ".git")) {
  git init -b main
}

$currentBranch = git branch --show-current
if (-not $currentBranch) { git checkout -b main }
elseif ($currentBranch -ne "main") { throw "Expected branch 'main', found '$currentBranch'. Resolve this explicitly before publishing." }

$existingOrigin = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0 -and $existingOrigin) {
  throw "An origin remote already exists: $existingOrigin. Refusing to overwrite it."
}

$repoExists = $false
try {
  gh repo view $FullName --json nameWithOwner *> $null
  $repoExists = $true
} catch { $repoExists = $false }
if ($repoExists) { throw "GitHub repository $FullName already exists. Refusing to overwrite it." }

$paths = @(
  ".editorconfig", ".gitignore", ".github", "AGENTS.md", "ASSET_INDEX.md",
  "GITHUB_REPOSITORY_SETUP.md", "README.md", "apps", "design-system", "docs",
  "examples", "package.json", "packages", "preview", "prompts", "pyproject.toml",
  "resources", "scripts"
)
git add -- $paths
if (-not (git diff --cached --quiet)) {
  git commit -m "chore: bootstrap IdlerDream reviewed baseline"
}

gh repo create $FullName --private --description "Local-first Windows dashboard for monitoring project workspaces and coding Agent processes." --source . --remote origin --push
Write-Host "Created and pushed https://github.com/$FullName"
