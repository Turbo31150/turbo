$h = hostname
$os = [System.Environment]::OSVersion.VersionString
$cpu = (Get-CimInstance Win32_Processor).Name
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB, 1)
$gpu = (Get-CimInstance Win32_VideoController).Name -join ', '
$disk = (Get-PSDrive -PSProvider FileSystem | ForEach-Object { $_.Name + ': ' + [math]::Round($_.Free/1GB,1).ToString() + 'GB free' }) -join '; '
$up = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$upStr = $up.Days.ToString() + 'j ' + $up.Hours.ToString() + 'h ' + $up.Minutes.ToString() + 'm'
$u = [Environment]::UserName
"$h|$os|$cpu|$ram|$gpu|$disk|$upStr|$u"
