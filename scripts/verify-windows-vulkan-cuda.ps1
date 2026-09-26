# Manual acceptance gate: requires native Windows with a CUDA-capable NVIDIA GPU.
# Uses synthetic media in an owned temporary directory; does not touch libraries.
param([Parameter(Mandatory=$true)][string]$Bundle)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$root = Join-Path $env:TEMP ('ersatzrs-row99-decode-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $root
function Invoke-Bounded([string]$Tool, [string]$Arguments) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = Join-Path $root $Tool
    $start.WorkingDirectory = $root
    $start.Arguments = $Arguments
    $start.UseShellExecute = $false
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $p = [Diagnostics.Process]::Start($start)
    try {
        $outTask = $p.StandardOutput.ReadToEndAsync()
        $errTask = $p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit(30000)) { $p.Kill(); $p.WaitForExit(); throw 'probe timed out' }
        $output = $outTask.GetAwaiter().GetResult()
        $errors = $errTask.GetAwaiter().GetResult()
        if ($p.ExitCode -ne 0) { throw "$Tool failed ($($p.ExitCode)): $errors" }
        return $output
    } finally { $p.Dispose() }
}
try {
    Copy-Item (Join-Path $Bundle 'ffmpeg.exe') $root
    Copy-Item (Join-Path $Bundle 'ffprobe.exe') $root
    Write-Output (Invoke-Bounded 'ffmpeg.exe' '-version').Split([Environment]::NewLine)[0]
    Get-FileHash -Algorithm SHA256 (Join-Path $root 'ffmpeg.exe') | Select-Object -ExpandProperty Hash
    $null = Invoke-Bounded 'ffmpeg.exe' '-hide_banner -nostdin -loglevel error -init_hw_device cuda=nv:0 -filter_hw_device nv -f lavfi -i testsrc2=size=320x240:duration=0.2:rate=5 -vf format=nv12,hwupload_cuda,scale_cuda=256:144 -c:v h264_nvenc -frames:v 1 -f null -'
    Write-Output 'CUDA/NVENC control passed.'
    $null = Invoke-Bounded 'ffmpeg.exe' '-hide_banner -nostdin -loglevel error -init_hw_device cuda=nv:0 -init_hw_device vulkan=vk@nv -filter_hw_device vk -f lavfi -i testsrc2=size=320x240:duration=0.2:rate=5 -vf format=yuv420p10le,hwupload,libplacebo=tonemapping=hable:colorspace=bt709:color_primaries=bt709:color_trc=bt709:format=nv12,sidedata=mode=delete:type=MASTERING_DISPLAY_METADATA,sidedata=mode=delete:type=CONTENT_LIGHT_LEVEL,sidedata=mode=delete:type=DOVI_RPU_BUFFER,sidedata=mode=delete:type=DOVI_METADATA,hwupload_cuda,scale_cuda=256:144 -c:v h264_nvenc -frames:v 1 -f null -'
    Write-Output 'ErsatzRS Vulkan/CUDA capability graph passed.'
    $null = Invoke-Bounded 'ffmpeg.exe' '-hide_banner -nostdin -loglevel error -init_hw_device cuda=nv:0 -init_hw_device vulkan=vk@nv -filter_hw_device vk -f lavfi -i testsrc2=size=320x240:duration=1:rate=25 -vf format=yuv420p10le,setparams=range=limited:color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc,hwupload,libplacebo=tonemapping=hable:colorspace=bt709:color_primaries=bt709:color_trc=bt709:format=nv12,sidedata=mode=delete:type=MASTERING_DISPLAY_METADATA,sidedata=mode=delete:type=CONTENT_LIGHT_LEVEL,sidedata=mode=delete:type=DOVI_RPU_BUFFER,sidedata=mode=delete:type=DOVI_METADATA,hwupload_cuda,scale_cuda=256:144 -c:v h264_nvenc -frames:v 25 -y output.mp4'
    $json = Invoke-Bounded 'ffprobe.exe' '-v error -select_streams v:0 -count_frames -show_entries stream=codec_name,width,height,color_space,color_transfer,color_primaries,nb_read_frames -of json output.mp4'
    $stream = ($json | ConvertFrom-Json).streams[0]
    if ($stream.codec_name -ne 'h264' -or $stream.width -ne 256 -or $stream.height -ne 144 -or $stream.nb_read_frames -ne '25') { throw 'wrong decoded stream dimensions, codec or frame count' }
    foreach ($field in 'color_space','color_transfer','color_primaries') {
        if ($stream.$field -ne 'bt709') { throw "wrong $field" }
    }
    $null = Invoke-Bounded 'ffmpeg.exe' '-hide_banner -nostdin -v error -xerror -i output.mp4 -f null -'
    Write-Output $json
    Write-Output 'Native Windows Vulkan/CUDA output: 25 decoded H.264 BT.709 frames, 256x144; decode passed.'
} finally {
    Remove-Item -Recurse -Force $root
}
