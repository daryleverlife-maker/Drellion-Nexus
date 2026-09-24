[Setup]
AppId={{E18F9D2B-2B7B-4C9E-A227-7D3B92E2A200}
AppName=Drellion Nexus 2 Alpha
AppVersion=2.0.0-alpha.1
DefaultDirName={autopf}\Drellion Nexus 2 Alpha
DefaultGroupName=Drellion Nexus 2 Alpha
OutputDir=..\installer-output
OutputBaseFilename=Drellion-Nexus-v2-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\DrellionNexus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Drellion Nexus 2 Alpha"; Filename: "{app}\DrellionNexus.exe"
Name: "{autodesktop}\Drellion Nexus 2 Alpha"; Filename: "{app}\DrellionNexus.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\DrellionNexus.exe"; Description: "Launch Drellion Nexus"; Flags: nowait postinstall skipifsilent
