' ============================================================
'  Vulcamoia Watcher — Arranque silencioso (sin ventana CMD)
'  Este archivo lanza watcher.py usando pythonw.exe (sin consola).
'  Doble clic o ejecutar via tarea programada.
' ============================================================

Dim fso, scriptDir, pythonw, watcherPy, shell

Set fso       = CreateObject("Scripting.FileSystemObject")
Set shell     = CreateObject("WScript.Shell")

' Directorio donde esta este .vbs (mismo que watcher.py)
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
watcherPy = scriptDir & "\watcher.py"

' pythonw.exe corre Python sin ventana de consola
' Si Python no esta en PATH, cambiar por la ruta completa:
' Ej: pythonw = "C:\Python313\pythonw.exe"
pythonw = "pythonw.exe"

' Verificar que watcher.py existe
If Not fso.FileExists(watcherPy) Then
    MsgBox "No se encontro watcher.py en:" & vbCrLf & scriptDir, vbCritical, "Vulcamoia Watcher"
    WScript.Quit 1
End If

' Lanzar sin ventana (0 = oculto, False = no esperar)
shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & watcherPy & Chr(34), 0, False

WScript.Quit 0
