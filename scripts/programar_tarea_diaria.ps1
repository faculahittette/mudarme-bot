# Crea (o actualiza) la tarea programada "mudarme-bot" para el usuario actual.
# Corre run_daily.bat todos los dias a las horas indicadas. No requiere admin.
#
#   - Si la compu esta bloqueada: corre igual (la sesion sigue iniciada).
#   - Si estaba suspendida: intenta despertarla (WakeToRun).
#   - Si estaba apagada a esa hora: corre apenas se prende (StartWhenAvailable).
#
# Uso: doble clic en programar_tarea_diaria.bat (en la raiz del repo).
param(
    [string[]]$Horas = @('12:00', '20:00'),
    [string]$Nombre = 'mudarme-bot'
)
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$bat = Join-Path $repo 'run_daily.bat'
if (-not (Test-Path $bat)) { throw "No encuentro $bat" }

# Ventana minimizada: no interrumpe si estas usando la compu.
$accion = New-ScheduledTaskAction -Execute 'cmd.exe' `
    -Argument "/c start `"mudarme-bot`" /min `"$bat`"" -WorkingDirectory $repo
$disparadores = $Horas | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparadores `
    -Settings $config -Description 'Busca deptos apto credito y los manda a Telegram' -Force | Out-Null

$tarea = Get-ScheduledTask -TaskName $Nombre
$info = $tarea | Get-ScheduledTaskInfo
Write-Host "Tarea '$Nombre' creada. Horarios: $($Horas -join ', ')."
Write-Host "Proxima corrida: $($info.NextRunTime)"
Write-Host "Para borrarla: Programador de tareas -> Biblioteca -> '$Nombre' -> Eliminar."
