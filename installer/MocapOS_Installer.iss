; MocapOS Professional Installer
; Built with Inno Setup 6
; Compatible with NVIDIA GPUs: 1000, 2000, 3000, 4000, 5000 series

#define MyAppName "MocapOS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MocapOS"
#define MyAppURL "https://mocapos.com"
#define MyAppExeName "MocapOS.exe"

[Setup]
AppId={{MOCAPOS-INSTALLER-2026}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={userpf}\MocapOS
DefaultGroupName=MocapOS
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=output
OutputBaseFilename=MocapOS_Setup_v1
SetupIconFile=..\assets\icon.ico
WizardImageFile=assets\wizard_image.bmp
WizardSmallImageFile=assets\wizard_small.bmp
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\assets\icon.ico
UninstallDisplayName=MocapOS
SetupLogging=yes
AlwaysShowComponentsList=no
DisableReadyPage=yes
DisableReadyMemo=yes
SetupMutex=MocapOS_Setup_Mutex

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,.git,.gitignore,outputs,*.mp4,*.avi,*.mov,*.pt,*.pth,*.ckpt,*.npz,*.pkl,*.tar.gz,*.tgz,*.zip,*.7z,*.rar,installer\output,docs\colab_example.ipynb,docs\example_video,hamer_lib\example_data,hamer_lib\_DATA,hamer_lib\docker,hamer_lib\third-party\ViTPose\configs,hamer_lib\third-party\ViTPose\demo,hamer_lib\third-party\ViTPose\tests,hamer_lib\third-party\ViTPose\tools,hamer_lib\third-party\ViTPose\mmpose,hamer_lib\third-party\ViTPose\.mim,inputs\checkpoints,*.md,*.yml,*.yaml,*.gif,*.jpg,*.jpeg,*.png"
Source: "scripts\detect_gpu.ps1"; DestDir: "{app}\installer\scripts"; Flags: ignoreversion
Source: "scripts\download_models.ps1"; DestDir: "{app}\installer\scripts"; Flags: ignoreversion
Source: "scripts\install_dependencies.ps1"; DestDir: "{app}\installer\scripts"; Flags: ignoreversion
Source: "scripts\run_step.cmd"; DestDir: "{app}\installer\scripts"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\MocapOS.vbs"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\MocapOS.vbs"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  InstallAborted: Boolean;
  InstallErrorMsg: String;
  SilentMode: Boolean;
  StepErrors: Array of String;

function IsSilent(): Boolean;
begin
  // WizardSilent() does NOT work in InitializeSetup because the wizard form
  // hasn't been created yet. Use command-line detection instead.
  Result := (Pos('/SILENT', Uppercase(GetCmdTail)) > 0) or (Pos('/VERYSILENT', Uppercase(GetCmdTail)) > 0);
end;

// Show SMPLX warning before installation starts (GUI only)
function InitializeSetup(): Boolean;
begin
  SilentMode := IsSilent;
  if not SilentMode then
  begin
    Result := MsgBox(
      'IMPORTANT LICENSE NOTICE' + #13#10 + #13#10 +
      'MocapOS uses the SMPL-X body model which requires a separate ' +
      'license from the Max Planck Institute.' + #13#10 + #13#10 +
      'You will need to:' + #13#10 +
      '1. Register at https://smpl-x.is.tue.mpg.de/' + #13#10 +
      '2. Download SMPL-X models (neutral, male, female)' + #13#10 +
      '3. Place them in the inputs/checkpoints/body_models/smplx/ folder' + #13#10 + #13#10 +
      'The installer will download all other components automatically.' + #13#10 + #13#10 +
      'This may take 30-60 minutes on a fresh system.' + #13#10 + #13#10 +
      'Do you want to continue?',
      mbConfirmation, MB_YESNO) = IDYES;
  end
  else
  begin
    Result := True;
  end;
  InstallAborted := False;
  InstallErrorMsg := '';
  SetArrayLength(StepErrors, 0);
end;

function RunStep(StepNum: Integer; StatusMsg: String): Boolean;
var
  ResultCode: Integer;
  CmdPath: String;
  Params: String;
  LogPath: String;
  FullMsg: String;
  ErrorDetail: String;
begin
  Result := False;
  
  if InstallAborted then
  begin
    Exit;
  end;
  
  CmdPath := ExpandConstant('{app}\installer\scripts\run_step.cmd');
  Params := IntToStr(StepNum);
  LogPath := ExpandConstant('{app}\installer\logs\MocapOS_Step' + IntToStr(StepNum) + '.log');
  
  FullMsg := StatusMsg + ' (Step ' + IntToStr(StepNum) + '/4)' + #13#10 +
             'This may take several minutes. Please wait...';
  
  WizardForm.StatusLabel.Caption := FullMsg;
  
  // Ensure log directory exists
  if not DirExists(ExpandConstant('{app}\installer\logs')) then
  begin
    if not CreateDir(ExpandConstant('{app}\installer\logs')) then
    begin
      ErrorDetail := 'Failed to create logs directory.';
      if not SilentMode then
        MsgBox(ErrorDetail, mbCriticalError, MB_OK)
      else
      begin
        SetArrayLength(StepErrors, GetArrayLength(StepErrors) + 1);
        StepErrors[GetArrayLength(StepErrors) - 1] := 'Step ' + IntToStr(StepNum) + ': ' + ErrorDetail;
      end;
      InstallAborted := True;
      Exit;
    end;
  end;
  
  if Exec(CmdPath, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      Result := True;
    end
    else
    begin
      ErrorDetail := 
        'Installation failed at Step ' + IntToStr(StepNum) + '.' + #13#10 + #13#10 +
        'Exit code: ' + IntToStr(ResultCode) + #13#10 + #13#10 +
        'Log file location:' + #13#10 +
        LogPath + #13#10 + #13#10 +
        'Common causes:' + #13#10 +
        '- Internet connection lost during download' + #13#10 +
        '- Antivirus blocked the installation' + #13#10 +
        '- Windows Script Host or PowerShell is disabled' + #13#10 +
        '- Not enough disk space' + #13#10 + #13#10 +
        'Please check the log file for details, then run the installer again.';
      
      if not SilentMode then
      begin
        InstallAborted := True;
        InstallErrorMsg := ErrorDetail;
        MsgBox(InstallErrorMsg, mbCriticalError, MB_OK);
      end
      else
      begin
        // In silent mode: log the error but continue installation
        SetArrayLength(StepErrors, GetArrayLength(StepErrors) + 1);
        StepErrors[GetArrayLength(StepErrors) - 1] := 'Step ' + IntToStr(StepNum) + ' failed with exit code ' + IntToStr(ResultCode);
        // Write error to a silent-mode error log
        SaveStringToFile(ExpandConstant('{app}\installer\logs\silent_errors.log'), 
          '[' + GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':') + '] ' + ErrorDetail + #13#10#13#10, True);
        // Allow installation to continue (partial install)
        Result := True;
      end;
    end;
  end
  else
  begin
    ErrorDetail := 
      'Failed to execute Step ' + IntToStr(StepNum) + '.' + #13#10 + #13#10 +
      'Could not run: ' + CmdPath + #13#10 + #13#10 +
      'This may be caused by:' + #13#10 +
      '- Antivirus blocking script execution' + #13#10 +
      '- Corrupted installer file' + #13#10 +
      '- Missing Windows components' + #13#10 + #13#10 +
      'Please re-download the installer and try again.';
    
    if not SilentMode then
    begin
      InstallAborted := True;
      InstallErrorMsg := ErrorDetail;
      MsgBox(InstallErrorMsg, mbCriticalError, MB_OK);
    end
    else
    begin
      // In silent mode: log the error but continue installation
      SetArrayLength(StepErrors, GetArrayLength(StepErrors) + 1);
      StepErrors[GetArrayLength(StepErrors) - 1] := 'Step ' + IntToStr(StepNum) + ' could not execute: ' + CmdPath;
      SaveStringToFile(ExpandConstant('{app}\installer\logs\silent_errors.log'), 
        '[' + GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':') + '] ' + ErrorDetail + #13#10#13#10, True);
      Result := True;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  UnblockResult: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Unblock scripts that may be blocked by Windows Zone.Identifier
    WizardForm.StatusLabel.Caption := 'Preparing installation scripts...';
    Exec('powershell.exe', '-ExecutionPolicy Bypass -Command "Unblock-File -Path ''' + ExpandConstant('{app}\installer\scripts\*') + '''"', '', SW_HIDE, ewWaitUntilTerminated, UnblockResult);
    
    // Step 1: Miniconda + Python environment
    if not RunStep(1, 'Installing Miniconda and Python environment...') then
    begin
      if not SilentMode then
      begin
        WizardForm.Close;
        Exit;
      end;
    end;
    
    // Step 2: PyTorch + CUDA + AI libraries
    if not RunStep(2, 'Installing PyTorch, CUDA, and AI libraries...') then
    begin
      if not SilentMode then
      begin
        WizardForm.Close;
        Exit;
      end;
    end;
    
    // Step 3: MocapOS packages + patches + models
    if not RunStep(3, 'Installing MocapOS packages and downloading AI models...') then
    begin
      if not SilentMode then
      begin
        WizardForm.Close;
        Exit;
      end;
    end;
    
    // Step 4: Verify installation
    if not RunStep(4, 'Verifying installation...') then
    begin
      if not SilentMode then
      begin
        WizardForm.Close;
        Exit;
      end;
    end;
  end;
end;

// Show SMPLX reminder on finished page
procedure CurPageChanged(CurPageID: Integer);
var
  PostInstallPath: String;
  SilentSummary: String;
  i: Integer;
begin
  if CurPageID = wpFinished then
  begin
    if InstallAborted then
    begin
      WizardForm.FinishedLabel.Caption :=
        'Installation could not be completed.' + #13#10 + #13#10 +
        InstallErrorMsg;
    end
    else if (SilentMode and (GetArrayLength(StepErrors) > 0)) then
    begin
      // Silent mode finished with partial errors
      SilentSummary := 
        'MocapOS has been installed, but some steps encountered errors.' + #13#10 + #13#10 +
        'Errors:' + #13#10;
      for i := 0 to GetArrayLength(StepErrors) - 1 do
      begin
        SilentSummary := SilentSummary + '- ' + StepErrors[i] + #13#10;
      end;
      SilentSummary := SilentSummary + #13#10 +
        'See {app}\installer\logs\silent_errors.log for details.' + #13#10 + #13#10 +
        'Next steps:' + #13#10 +
        '1. Download SMPL-X from https://smpl-x.is.tue.mpg.de/' + #13#10 +
        '2. Place .npz files in: inputs\checkpoints\body_models\smplx\' + #13#10 +
        '3. Launch MocapOS from the Start Menu or Desktop!';
      WizardForm.FinishedLabel.Caption := SilentSummary;
    end
    else
    begin
      PostInstallPath := ExpandConstant('{app}\POST_INSTALL_STEPS.txt');
      
      if FileExists(PostInstallPath) then
      begin
        WizardForm.FinishedLabel.Caption :=
          'MocapOS has been installed!' + #13#10 + #13#10 +
          'IMPORTANT: Some components could not be installed automatically.' + #13#10 +
          'This usually happens on fresh Windows installations without a C++ compiler.' + #13#10 + #13#10 +
          'Next steps:' + #13#10 +
          '1. Install Visual Studio Build Tools (see POST_INSTALL_STEPS.txt)' + #13#10 +
          '2. Download SMPL-X from https://smpl-x.is.tue.mpg.de/' + #13#10 +
          '3. Place .npz files in: inputs\checkpoints\body_models\smplx\' + #13#10 +
          '4. Launch MocapOS from the Start Menu or Desktop!';
      end
      else
      begin
        WizardForm.FinishedLabel.Caption :=
          'MocapOS has been installed!' + #13#10 + #13#10 +
          'Next steps:' + #13#10 +
          '1. Download SMPL-X from https://smpl-x.is.tue.mpg.de/' + #13#10 +
          '2. Place .npz files in: inputs\checkpoints\body_models\smplx\' + #13#10 +
          '3. Launch MocapOS from the Start Menu or Desktop!';
      end;
    end;
    WizardForm.FinishedLabel.Font.Style := [];
  end;
end;

// Check GPU before installation (GUI only)
function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
  ScriptPath: String;
  OutputFile: String;
begin
  Result := True;
  
  if CurPageID = wpWelcome then
  begin
    if SilentMode then
    begin
      // Skip GPU check dialog in silent mode
      Exit;
    end;
    
    ScriptPath := ExpandConstant('{tmp}\detect_gpu.ps1');
    OutputFile := ExpandConstant('{tmp}\gpu_info.txt');
    
    ExtractTemporaryFile('detect_gpu.ps1');
    
    if FileExists(ScriptPath) then
    begin
      if Exec('powershell.exe', '-ExecutionPolicy Bypass -NoProfile -File "' + ScriptPath + '" -OutputFile "' + OutputFile + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      begin
        MsgBox(
          'GPU check complete.' + #13#10 + #13#10 +
          'The installer will install the appropriate PyTorch version.' + #13#10 +
          'Note: RTX 5000 series users may need manual adjustment.' + #13#10 + #13#10 +
          'Installation time: ~30-60 minutes on first run.',
          mbInformation, MB_OK);
      end;
    end;
  end;
end;
