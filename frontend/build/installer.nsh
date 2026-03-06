; 卸载前将用户数据备份到 %APPDATA%/econ-agent/data/
; 防止 NSIS RMDir /r 删除安装目录时丢失用户数据

!macro customUnInstall
  ; 备份目标：%APPDATA%/econ-agent/data/
  CreateDirectory "$APPDATA\econ-agent\data"

  ; 从安装目录 resources/app/data/ 迁移数据文件
  IfFileExists "$INSTDIR\resources\app\data\memories.db" 0 _skip_memories
    IfFileExists "$APPDATA\econ-agent\data\memories.db" _skip_memories 0
      CopyFiles /SILENT "$INSTDIR\resources\app\data\memories.db" "$APPDATA\econ-agent\data\"
  _skip_memories:

  IfFileExists "$INSTDIR\resources\app\data\checkpoints.db" 0 _skip_checkpoints
    IfFileExists "$APPDATA\econ-agent\data\checkpoints.db" _skip_checkpoints 0
      CopyFiles /SILENT "$INSTDIR\resources\app\data\checkpoints.db" "$APPDATA\econ-agent\data\"
  _skip_checkpoints:

  IfFileExists "$INSTDIR\resources\app\data\settings.json" 0 _skip_settings
    IfFileExists "$APPDATA\econ-agent\data\settings.json" _skip_settings 0
      CopyFiles /SILENT "$INSTDIR\resources\app\data\settings.json" "$APPDATA\econ-agent\data\"
  _skip_settings:

  IfFileExists "$INSTDIR\resources\app\data\store.db" 0 _skip_store
    IfFileExists "$APPDATA\econ-agent\data\store.db" _skip_store 0
      CopyFiles /SILENT "$INSTDIR\resources\app\data\store.db" "$APPDATA\econ-agent\data\"
  _skip_store:

  ; 迁移 workspace 目录（用户的报告、笔记等工作成果）
  IfFileExists "$INSTDIR\resources\app\data\workspace\*.*" 0 _skip_workspace
    IfFileExists "$APPDATA\econ-agent\data\workspace\*.*" _skip_workspace 0
      CreateDirectory "$APPDATA\econ-agent\data\workspace"
      CopyFiles /SILENT "$INSTDIR\resources\app\data\workspace\*.*" "$APPDATA\econ-agent\data\workspace\"
  _skip_workspace:

  ; 迁移 skills 目录
  IfFileExists "$INSTDIR\resources\app\skills\*.*" 0 _skip_skills
    IfFileExists "$APPDATA\econ-agent\data\skills\*.*" _skip_skills 0
      CreateDirectory "$APPDATA\econ-agent\data\skills"
      CopyFiles /SILENT "$INSTDIR\resources\app\skills\*.*" "$APPDATA\econ-agent\data\skills\"
  _skip_skills:
!macroend
