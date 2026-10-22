param([string]$Action='Inspect')
$ErrorActionPreference='Stop'
$api='E:/Program Files/SOLIDWORKS Corp/SOLIDWORKS/api/redist'
$a=Join-Path $api 'SolidWorks.Interop.sldworks.dll'
$b=Join-Path $api 'SolidWorks.Interop.swconst.dll'
[void][Reflection.Assembly]::LoadFrom($a)
[void][Reflection.Assembly]::LoadFrom($b)
Add-Type -Path (Join-Path $PSScriptRoot 'revise_solidworks.cs') -ReferencedAssemblies $a,$b
[RobotRevision]::Run((Split-Path $PSScriptRoot -Parent),$Action)
