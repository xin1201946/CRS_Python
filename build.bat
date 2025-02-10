@echo off
echo 正在尝试构建...
echo.

:: 检查虚拟环境是否存在
if not exist ".\.venv\Scripts\python.exe" (
    echo 虚拟环境不存在，请先创建虚拟环境！
    pause
    exit /b
)

:: 构建程序
".\.venv\Scripts\python.exe" -m nuitka --standalone --follow-imports --output-dir=.\dist --enable-plugin=no-qt --include-module=yolov5 --include-module=ultralytics --include-module=tensorflow --module-parameter=torch-disable-jit=yes --windows-icon-from-ico=.\CCRS.ico --windows-product-name="CCRS" --windows-file-description="Casting Char Recognition System" --product-version=2.0.0 --file-version=2.0.2 --output-filename=CCRS main.py

cls

echo 构建完成
echo.
echo 进行最后的操作...
echo 请不要关闭窗口

:: 复制必要的文件夹和文件
xcopy ".\.venv\Lib\site-packages\ultralytics" ".\dist\main.dist\ultralytics" /E /I /Y
xcopy ".\.venv\Lib\site-packages\ultralytics_thop-2.0.14.dist-info" ".\dist\main.dist\ultralytics_thop-2.0.14.dist-info" /E /I /Y
xcopy ".\.venv\Lib\site-packages\ultralytics-8.3.63.dist-info" ".\dist\main.dist\ultralytics-8.3.63.dist-info" /E /I /Y
xcopy ".\.venv\Lib\site-packages\yolov5" ".\dist\main.dist\yolov5" /E /I /Y
xcopy ".\.venv\Lib\site-packages\yolov5-7.0.14.dist-info" ".\dist\main.dist\yolov5-7.0.14.dist-info" /E /I /Y
xcopy ".\.venv\Lib\site-packages\yolov5\models" ".\dist\main.dist\models" /E /I /Y

:: 复制其他文件夹和文件
xcopy ".\library" ".\dist\main.dist\library" /E /I /Y
copy ".\getNum.py" ".\dist\main.dist\getNum.py" /Y
xcopy ".\flask-dist" ".\dist\main.dist\flask-dist" /E /I /Y

cls
echo 最后步骤完成
echo.
echo 准备启动中...

:: 启动程序
.\dist\main.dist\CCRS.exe --simulate --nogui

if errorlevel 1 (
    echo 程序启动失败，返回错误信息！
) else (
    echo 程序正常启动，返回状态码 0！
)

pause