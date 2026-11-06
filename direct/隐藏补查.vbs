Option Explicit
If WScript.Arguments.Count <> 1 Then WScript.Quit 2
Dim shell, command, result
Set shell = CreateObject("WScript.Shell")
command = Chr(34) & shell.ExpandEnvironmentStrings("%ComSpec%") & Chr(34) & " /d /c " & Chr(34) & Chr(34) & WScript.Arguments(0) & Chr(34) & Chr(34)
result = shell.Run(command, 0, True)
WScript.Quit result
