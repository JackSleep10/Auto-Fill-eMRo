Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\Project dashboard"
WshShell.Run "C:\Python313\pythonw.exe main.py", 0, False
