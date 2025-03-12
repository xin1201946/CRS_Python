@echo off

echo 正在尝试构建...
echo.

:: 检查虚拟环境是否存在
if not exist ".\.venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先创建虚拟环境！
    pause
    exit /b
)

:: 构建程序
".\.venv\Scripts\python.exe" -m nuitka ^
    --standalone ^
    --follow-imports ^
    --nofollow-import-to=IPython ^
    --output-dir=.\dist ^
    --enable-plugin=no-qt ^
    --include-module=ultralytics ^
    --include-module=CCRS_Library ^
    --include-module=tensorflow ^
    --module-parameter=torch-disable-jit=no ^
    --windows-icon-from-ico=.\CCRS.ico ^
    --windows-product-name="CCRS" ^
    --windows-file-description="Casting Char Recognition System" ^
    --product-version=2.0.5 ^
    --file-version=2.0.5 ^
    --output-filename=CCRS ^
    main.py 

echo 构建完成！
echo.
echo 进行最后的文件复制...
echo 请不要关闭窗口
:: 复制 Python 依赖文件夹
set SRC_DIR=.venv\Lib\site-packages
set DST_DIR=.\dist\main.dist

for %%D in (ultralytics CCRS_Library yolov5 yolov5\models torch torchaudio torchgen torchvision) do (
    if exist "%SRC_DIR%\%%D" (
        echo 复制 %%D ...
        xcopy "%SRC_DIR%\%%D" "%DST_DIR%\%%D" /E /I /Y >nul
    ) else (
        echo [警告] 未找到 %SRC_DIR%\%%D，跳过复制！
    )
)

:: 复制独立文件
if exist ".\getNum.py" (
    copy ".\getNum.py" "%DST_DIR%\getNum.py" /Y >nul
)

if exist ".\flask-dist" (
    xcopy ".\flask-dist" "%DST_DIR%\flask-dist" /E /I /Y >nul
)

echo 最后步骤完成！
echo.
echo 准备启动 CCRS...

:: 启动程序
"%DST_DIR%\CCRS.exe" --simulate

if errorlevel 1 (
    echo [错误] 程序启动失败！
) else (
    echo [成功] 程序正常启动！
)

pause
