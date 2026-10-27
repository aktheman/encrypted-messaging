; NSIS Installer Script for Encrypted Messaging App
; Generates a Windows installer for all three executables

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

; Application info
Name "Encrypted Messaging"
OutFile "EncryptedMessaging-Setup.exe"
InstallDir "$PROGRAMFILES\Encrypted Messaging"
InstallDirRegKey HKCU "Software\EncryptedMessaging" ""
RequestExecutionLevel admin

; Icon
Icon "icon.ico"

; Modern UI
!define MUI_ABORTWARNING
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; Components
Section "Core Files" SEC_CORE
    SectionIn RO
    SetOutPath "$INSTDIR"
    File "dist\encrypted-messaging-gui\encrypted-messaging-gui.exe"
    File "dist\encrypted-messaging-tui\encrypted-messaging-tui.exe"
    File "dist\encrypted-messaging-server\encrypted-messaging-server.exe"
SectionEnd

Section "GUI Application" SEC_GUI
    SetOutPath "$INSTDIR"
    CreateDirectory "$SMPROGRAMS\Encrypted Messaging"
    CreateShortcut "$SMPROGRAMS\Encrypted Messaging\Encrypted Messaging GUI.lnk" "$INSTDIR\encrypted-messaging-gui.exe"
    CreateShortcut "$DESKTOP\Encrypted Messaging GUI.lnk" "$INSTDIR\encrypted-messaging-gui.exe"
SectionEnd

Section "TUI Application" SEC_TUI
    SetOutPath "$INSTDIR"
    CreateDirectory "$SMPROGRAMS\Encrypted Messaging"
    CreateShortcut "$SMPROGRAMS\Encrypted Messaging\Encrypted Messaging TUI.lnk" "$INSTDIR\encrypted-messaging-tui.exe"
SectionEnd

Section "Server Application" SEC_SERVER
    SetOutPath "$INSTDIR"
    CreateDirectory "$SMPROGRAMS\Encrypted Messaging"
    CreateShortcut "$SMPROGRAMS\Encrypted Messaging\Encrypted Messaging Server.lnk" "$INSTDIR\encrypted-messaging-server.exe"
SectionEnd

Section "Documentation" SEC_DOCS
    SetOutPath "$INSTDIR\docs"
    File "README.md"
    File "CHANGELOG.md"
    CreateShortcut "$SMPROGRAMS\Encrypted Messaging\Documentation.lnk" "$INSTDIR\docs\README.md"
SectionEnd

; Uninstaller
Section "Uninstall"
    Delete "$INSTDIR\encrypted-messaging-gui.exe"
    Delete "$INSTDIR\encrypted-messaging-tui.exe"
    Delete "$INSTDIR\encrypted-messaging-server.exe"
    Delete "$INSTDIR\docs\README.md"
    Delete "$INSTDIR\docs\CHANGELOG.md"
    RMDir "$INSTDIR\docs"
    RMDir "$INSTDIR"
    Delete "$SMPROGRAMS\Encrypted Messaging\Encrypted Messaging GUI.lnk"
    Delete "$SMPROGRAMS\Encrypted Messaging\Encrypted Messaging TUI.lnk"
    Delete "$SMPROGRAMS\Encrypted Messaging\Encrypted Messaging Server.lnk"
    Delete "$SMPROGRAMS\Encrypted Messaging\Documentation.lnk"
    RMDir "$SMPROGRAMS\Encrypted Messaging"
    Delete "$DESKTOP\Encrypted Messaging GUI.lnk"
    DeleteRegKey HKCU "Software\EncryptedMessaging"
SectionEnd

Function .onInit
    ; Check for previous installation
    ReadRegStr $0 HKCU "Software\EncryptedMessaging" ""
    StrCmp $0 "" 0 +2
    MessageBox MB_OK "Encrypted Messaging is already installed. The installer will update it."
FunctionEnd

Function .onInstSuccess
    WriteRegStr HKCU "Software\EncryptedMessaging" "" "$INSTDIR"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\EncryptedMessaging" "DisplayName" "Encrypted Messaging"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\EncryptedMessaging" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\EncryptedMessaging" "DisplayIcon" "$INSTDIR\encrypted-messaging-gui.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\EncryptedMessaging" "DisplayVersion" "1.0.0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\EncryptedMessaging" "Publisher" "Encrypted Messaging Project"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\EncryptedMessaging" "URLInfoAbout" "https://github.com/encrypted-messaging"
FunctionEnd