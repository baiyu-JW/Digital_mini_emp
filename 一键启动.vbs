Set WshShell = CreateObject("WScript.Shell") 
WshShell.CurrentDirectory = "D:\Digital_mini_emp" 
WshShell.Run "cmd /c python main.py", 0, False 
