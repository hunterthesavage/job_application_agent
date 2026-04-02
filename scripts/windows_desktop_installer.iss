#ifndef AppVersion
  #define AppVersion "1.0.2"
#endif

#ifndef RepoRoot
  #error RepoRoot must be provided to the installer build.
#endif

#define AppName "Job Application Agent"
#define AppExeName "JobApplicationAgentDesktop.exe"
#define PackageDir AddBackslash(RepoRoot) + "dist\\windows-desktop\\JobApplicationAgentDesktop"
#define OutputDirPath AddBackslash(RepoRoot) + "dist\\windows-desktop"

[Setup]
AppId={{0DEB59FD-546C-4A1C-88EA-0E57A9495D10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Hunter Savage
DefaultDirName={autopf}\Job Application Agent
DefaultGroupName=Job Application Agent
DisableDirPage=yes
Compression=lzma
SolidCompression=yes
OutputDir={#OutputDirPath}
OutputBaseFilename=JobApplicationAgentDesktop-setup-{#AppVersion}
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Job Application Agent"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Job Application Agent"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Job Application Agent"; Flags: nowait postinstall skipifsilent
