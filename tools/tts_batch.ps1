# Generates voice lines with the free built-in Windows voices (offline).
# Usage: powershell -ExecutionPolicy Bypass -File tools\tts_batch.ps1 <jobs.json>
# jobs.json: [{"out": "D:\\...\\line.wav", "voice": "Microsoft David Desktop", "rate": 0, "pitch": "-10%", "text": "..."}]
param([string]$Jobs)
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$list = Get-Content -Raw -Encoding UTF8 $Jobs | ConvertFrom-Json
$done = 0
foreach ($job in $list) {
    $synth.SelectVoice($job.voice)
    $synth.Rate = [int]$job.rate
    $text = [System.Security.SecurityElement]::Escape($job.text)
    $ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><prosody pitch='$($job.pitch)'>$text</prosody></speak>"
    $synth.SetOutputToWaveFile($job.out, $format)
    $synth.SpeakSsml($ssml)
    $synth.SetOutputToNull()
    $done++
}
Write-Output "generated $done"
