param([switch]$PullModel)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$portable=Join-Path $projectRoot '.local/ollama/ollama.exe'
$installed=Get-Command ollama -ErrorAction SilentlyContinue
if(Test-Path -LiteralPath $portable) { $runtimePath=$portable }
elseif($installed) { $runtimePath=$installed.Source }
else { throw 'Install the local runtime using docs/ENVIRONMENT_SETUP.md first.' }
$env:OLLAMA_HOST='127.0.0.1:11434'
$env:OLLAMA_MODELS=Join-Path $projectRoot '.local/models'
$env:OLLAMA_NO_CLOUD='1'
New-Item -ItemType Directory -Force (Join-Path $projectRoot '.local') | Out-Null
try { $null=Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 }
catch {
    $launch=@{
        FilePath=$runtimePath
        ArgumentList='serve'
        WindowStyle='Hidden'
        PassThru=$true
        RedirectStandardOutput=(Join-Path $projectRoot '.local/ollama-server.out.log')
        RedirectStandardError=(Join-Path $projectRoot '.local/ollama-server.err.log')
    }
    $runtimeProcess=Start-Process @launch
    $runtimeProcess.Id | Set-Content (Join-Path $projectRoot '.local/ollama-server.pid')
    $ready=$false
    for($attempt=0;$attempt -lt 40;$attempt++) {
        try { $null=Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 1; $ready=$true; break }
        catch { Start-Sleep -Milliseconds 250 }
    }
    if(-not $ready) { throw 'The local model runtime did not become ready. Check the .local runtime logs.' }
}
if($PullModel) {
    & $runtimePath pull qwen2.5:1.5b
    if($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
}
$body=@{model='qwen2.5:1.5b';messages=@();stream=$false;keep_alive='5m'} | ConvertTo-Json -Depth 5
$null=Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/chat' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 60
Write-Output 'Local Qwen2.5 1.5B is ready on 127.0.0.1:11434.'
