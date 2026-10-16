# Applies every sql/*.sql file, in name order, to the ClickHouse container.
# Safe to re-run: every statement is CREATE OR REPLACE VIEW.
$container = "slack-ingestion-service-clickhouse"

Get-ChildItem (Join-Path $PSScriptRoot "../sql") -Filter *.sql | Sort-Object Name | ForEach-Object {
    Write-Host "applying $($_.Name)"
    Get-Content $_.FullName | docker exec -i $container clickhouse-client --password default --multiquery
    if ($LASTEXITCODE -ne 0) { throw "failed: $($_.Name)" }
}
Write-Host "done"
