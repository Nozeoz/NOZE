# Installer Jarvis untuk Windows.
# Jalankan di PowerShell biasa (bukan Administrator):
#   irm https://raw.githubusercontent.com/Nozeoz/NOZE/claude/pensive-maxwell-phq5pl/setup.ps1 | iex

$ErrorActionPreference = "Stop"
$Branch = "claude/pensive-maxwell-phq5pl"
$Repo = "https://github.com/Nozeoz/NOZE"
$Dir = Join-Path $HOME "Documents\NOZE"

function Say($text) { Write-Host "`n>> $text" -ForegroundColor Cyan }
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "`n  JARVIS - installer`n" -ForegroundColor Cyan

# 1. Git + Node.js
if (-not (Has "git")) {
  Say "Git belum ada, menginstall lewat winget..."
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
  Refresh-Path
}
$nodeOk = $false
if (Has "node") {
  $major = [int]((node -v).TrimStart("v").Split(".")[0])
  $nodeOk = $major -ge 22
}
if (-not $nodeOk) {
  Say "Node.js (versi 22+) belum ada, menginstall lewat winget..."
  winget install --id OpenJS.NodeJS.LTS -e --source winget --accept-package-agreements --accept-source-agreements
  Refresh-Path
}
if (-not (Has "git") -or -not (Has "node")) {
  Write-Host "`nGit/Node.js sudah diinstall tapi belum terbaca. Tutup PowerShell, buka lagi, lalu jalankan perintah installer yang sama sekali lagi." -ForegroundColor Yellow
  return
}

# 2. Download / update kode
if (Test-Path (Join-Path $Dir ".git")) {
  Say "Jarvis sudah ada di $Dir, mengambil versi terbaru..."
  git -C $Dir fetch origin $Branch
  git -C $Dir checkout $Branch
  git -C $Dir pull --ff-only origin $Branch
} else {
  Say "Mendownload Jarvis ke $Dir ..."
  git clone -b $Branch $Repo $Dir
}
Set-Location $Dir

# 3. Library (npm.cmd dipakai supaya tidak kena blokir execution policy)
Say "Menginstall library (bisa 1-2 menit)..."
npm.cmd install --no-audit --no-fund

# 4. File .env
$envFile = Join-Path $Dir ".env"
if (-not (Test-Path $envFile)) {
  Say "Pengaturan awal"
  Write-Host "API key dibuat di https://console.anthropic.com -> API Keys -> Create Key"
  $key = Read-Host "Paste ANTHROPIC_API_KEY (klik kanan untuk paste, lalu Enter)"
  $name = Read-Host "Nama lu"
  $call = Read-Host "Jarvis manggil lu apa? (Enter = Tuan)"
  if (-not $call) { $call = "Tuan" }

  $text = Get-Content (Join-Path $Dir ".env.example") -Raw
  $text = $text -replace "(?m)^ANTHROPIC_API_KEY=.*$", "ANTHROPIC_API_KEY=$($key.Trim())"
  $text = $text -replace "(?m)^OWNER_NAME=.*$", "OWNER_NAME=$($name.Trim())"
  $text = $text -replace "(?m)^OWNER_HONORIFIC=.*$", "OWNER_HONORIFIC=$($call.Trim())"
  [IO.File]::WriteAllText($envFile, $text, (New-Object Text.UTF8Encoding $false))
  Write-Host "Tersimpan di $envFile (file ini tidak ikut ke GitHub)."
} else {
  Say ".env sudah ada, tidak diubah."
}

# 5. Shortcut di Desktop
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop "Jarvis.lnk"))
$shortcut.TargetPath = Join-Path $Dir "Jarvis.bat"
$shortcut.WorkingDirectory = $Dir
$shortcut.Save()
Say "Shortcut 'Jarvis' dibuat di Desktop. Lain kali tinggal double-click itu."

# 6. Nyalakan
Say "Menyalakan Jarvis... (tutup jendela ini untuk mematikan)"
Start-Process -FilePath (Join-Path $Dir "Jarvis.bat") -WorkingDirectory $Dir
