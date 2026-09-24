[Setup]
AppId={{BFA6CE74-57CA-4F8F-B4A6-D6A7B7985A5A}
AppName=Drellion Nexus
AppVersion=2.0.3
DefaultDirName={autopf}\Drellion Nexus
DefaultGroupName=Drellion Nexus
OutputDir=..\installer-output
OutputBaseFilename=Drellion-Nexus-2.0-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Files]
Source: "..\dist\DrellionNexus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Drellion Nexus"; Filename: "{app}\DrellionNexus.exe"
Name: "{autodesktop}\Drellion Nexus"; Filename: "{app}\DrellionNexus.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\DrellionNexus.exe"; Description: "Launch Drellion Nexus 2.0"; Flags: nowait postinstall skipifsilent
