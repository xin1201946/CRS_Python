@echo off
chcp 65001 >nul  & REM 解决乱码问题

echo 正在编译...
echo.

:: 检查 Python 是否存在
if not exist ".\.venv\Scripts\python.exe" (
    echo [错误] Python 解释器不存在，请先安装虚拟环境！
    pause
    exit /b
)

:: Nuitka 编译
".\.venv\Scripts\python.exe" -m nuitka ^
    --standalone ^
    --follow-imports ^
    --output-dir=.\dist ^
    --enable-plugin=no-qt ^
    --include-module=ultralytics ^
    --include-module=CCRS_Library ^
    --include-package=torch ^
    --include-package=torchvision ^
    --include-module=tensorflow ^
    --module-parameter=torch-disable-jit=no ^
    --windows-icon-from-ico=.\CCRS.ico ^
    --windows-product-name="CCRS" ^
    --windows-file-description="Casting Char Recognition System" ^
    --product-version=2.0.5 ^
    --file-version=2.0.5 ^
    --lto=no ^
    --output-filename=CCRS ^
    --assume-yes-for-downloads ^
    main.py 

echo 编译完成！
echo.
echo 现在开始复制必要的文件...

:: 复制 Python 依赖
set SRC_DIR=.venv\Lib\site-packages
set DST_DIR=.\dist\main.dist

for %%D in (ultralytics CCRS_Library yolov5 yolov5\models torch torchaudio torchgen torchvision) do (
    if exist "%SRC_DIR%\%%D" (
        echo 复制 %%D ...
        xcopy "%SRC_DIR%\%%D" "%DST_DIR%\%%D" /E /I /Y >nul
    ) else (
        echo [警告] 未找到 %SRC_DIR%\%%D，跳过！
    )
)

:: 复制 Flask 相关文件
if exist ".\flask-dist" (
    xcopy ".\flask-dist" "%DST_DIR%\flask-dist" /E /I /Y >nul
)

echo 复制完成！
echo.
echo 现在启动 CCRS...

:: 运行程序
"%DST_DIR%\CCRS.exe" --simulate

if errorlevel 1 (
    echo [错误] 运行失败！
) else (
    echo [成功] 程序启动成功！
)

pause
