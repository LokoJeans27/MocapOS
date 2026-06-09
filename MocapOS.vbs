' MocapOS Launcher - silent execution with error handling
' Searches multiple locations for the Python environment
Dim WshShell, FSO, ScriptDir, PythonPath, GuiPath, SearchPaths

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
GuiPath = ScriptDir & "\gvhmr_gui.py"

' Check for post-install instructions
Dim PostInstallFile
PostInstallFile = ScriptDir & "\POST_INSTALL_STEPS.txt"

' Build list of locations to search for pythonw.exe
' The portable bundle ships a self-contained env at <app>\env, which must win
' so the app never depends on a system-wide conda install.
SearchPaths = Array( _
    ScriptDir & "\env\pythonw.exe", _
    WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\miniconda3\envs\gvhmr\pythonw.exe", _
    WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\miniconda3\envs\gvhmr\pythonw.exe", _
    "C:\miniconda3\envs\gvhmr\pythonw.exe", _
    WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\anaconda3\envs\gvhmr\pythonw.exe", _
    WshShell.ExpandEnvironmentStrings("%ALLUSERSPROFILE%") & "\miniconda3\envs\gvhmr\pythonw.exe", _
    WshShell.ExpandEnvironmentStrings("%PROGRAMDATA%") & "\miniconda3\envs\gvhmr\pythonw.exe", _
    WshShell.ExpandEnvironmentStrings("%PUBLIC%") & "\miniconda3\envs\gvhmr\pythonw.exe" _
)

' Try each known location
PythonPath = ""
Dim i
For i = 0 To UBound(SearchPaths)
    If FSO.FileExists(SearchPaths(i)) Then
        PythonPath = SearchPaths(i)
        Exit For
    End If
Next

' Also try to find via PATH
If PythonPath = "" Then
    Dim PathPython
    PathPython = FindPythonInPath()
    If PathPython <> "" Then
        PythonPath = PathPython
    End If
End If

' Still not found - show detailed error
If PythonPath = "" Then
    Dim ErrorMsg
    ErrorMsg = "MocapOS cannot start because the Python environment was not found." & vbCrLf & vbCrLf & _
               "The installer should have created:" & vbCrLf & _
               "  %USERPROFILE%\miniconda3\envs\gvhmr\pythonw.exe" & vbCrLf & vbCrLf & _
               "Searched locations:" & vbCrLf
    
    For i = 0 To UBound(SearchPaths)
        ErrorMsg = ErrorMsg & "  " & SearchPaths(i) & vbCrLf
    Next
    
    ErrorMsg = ErrorMsg & vbCrLf & _
               "Common causes:" & vbCrLf & _
               "  1. The installer was cancelled before completing all steps." & vbCrLf & _
               "  2. The installer was run as Administrator, installing Miniconda" & vbCrLf & _
               "     in the Admin profile instead of your user profile." & vbCrLf & _
               "  3. Miniconda was installed to a custom location." & vbCrLf & vbCrLf & _
               "Solutions:" & vbCrLf & _
               "  - Re-run the installer and let it complete all 4 steps." & vbCrLf & _
               "  - Or run the installer WITHOUT 'Run as Administrator'." & vbCrLf & _
               "  - Or install manually using install.bat in the app folder."
    
    MsgBox ErrorMsg, vbCritical, "MocapOS - Environment Not Found"
    WScript.Quit 1
End If

' Check if GUI script exists
If Not FSO.FileExists(GuiPath) Then
    MsgBox "MocapOS cannot find the main application file:" & vbCrLf & GuiPath & vbCrLf & vbCrLf & _
           "Please reinstall MocapOS.", _
           vbCritical, "MocapOS - File Not Found"
    WScript.Quit 1
End If

' Check for post-install steps
If FSO.FileExists(PostInstallFile) Then
    Dim ts, postContent
    Set ts = FSO.OpenTextFile(PostInstallFile, 1, False)
    postContent = ts.ReadAll
    ts.Close
    
    Dim postMsg
    postMsg = "MocapOS core is installed and ready to use." & vbCrLf & vbCrLf & _
              "However, some optional components could not be installed automatically." & vbCrLf & _
              "The app will launch, but certain features may be limited until you complete" & vbCrLf & _
              "the additional installation steps." & vbCrLf & vbCrLf & _
              "A detailed guide has been saved to:" & vbCrLf & PostInstallFile & vbCrLf & vbCrLf & _
              "Do you want to open the guide now?"
    
    Dim result
    result = MsgBox(postMsg, vbExclamation + vbYesNo, "MocapOS - Additional Steps Required")
    If result = vbYes Then
        WshShell.Run "notepad.exe """ & PostInstallFile & """"
    End If
End If

' Launch silently
WshShell.CurrentDirectory = ScriptDir
WshShell.Run Chr(34) & PythonPath & Chr(34) & " " & Chr(34) & GuiPath & Chr(34), 0, False

Set WshShell = Nothing
Set FSO = Nothing

' Helper function: try to find pythonw via PATH
Function FindPythonInPath()
    Dim tempFile, cmd, result, foundPath
    foundPath = ""
    
    tempFile = WshShell.ExpandEnvironmentStrings("%TEMP%") & "\mocapos_where_python.txt"
    
    ' Try 'where pythonw' first
    cmd = "cmd /c where pythonw > """ & tempFile & """ 2>nul"
    WshShell.Run cmd, 0, True
    
    If FSO.FileExists(tempFile) Then
        Dim ts2
        Set ts2 = FSO.OpenTextFile(tempFile, 1, False)
        If Not ts2.AtEndOfStream Then
            result = Trim(ts2.ReadLine)
            If result <> "" And InStr(LCase(result), "gvhmr") > 0 Then
                foundPath = result
            End If
        End If
        ts2.Close
        FSO.DeleteFile(tempFile)
    End If
    
    FindPythonInPath = foundPath
End Function
