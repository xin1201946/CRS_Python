@echo off
echo ���ڳ��Թ���...
echo.

:: ������⻷���Ƿ����
if not exist ".\.venv\Scripts\python.exe" (
    echo ���⻷�������ڣ����ȴ������⻷����
    pause
    exit /b
)

:: ��������
".\.venv\Scripts\python.exe" -m nuitka --standalone --follow-imports --output-dir=.\dist --enable-plugin=no-qt --include-module=yolov5 --include-module=ultralytics --include-module=tensorflow --module-parameter=torch-disable-jit=yes --windows-icon-from-ico=.\CCRS.ico --windows-product-name="CCRS" --windows-file-description="Casting Char Recognition System" --product-version=2.0.0 --file-version=2.0.2 --output-filename=CCRS main.py

cls

echo �������
echo.
echo �������Ĳ���...
echo �벻Ҫ�رմ���

:: ���Ʊ�Ҫ���ļ��к��ļ�
xcopy ".\.venv\Lib\site-packages\ultralytics" ".\dist\main.dist\ultralytics" /E /I /Y
xcopy ".\.venv\Lib\site-packages\ultralytics_thop-2.0.14.dist-info" ".\dist\main.dist\ultralytics_thop-2.0.14.dist-info" /E /I /Y
xcopy ".\.venv\Lib\site-packages\ultralytics-8.3.63.dist-info" ".\dist\main.dist\ultralytics-8.3.63.dist-info" /E /I /Y
xcopy ".\.venv\Lib\site-packages\yolov5" ".\dist\main.dist\yolov5" /E /I /Y
xcopy ".\.venv\Lib\site-packages\yolov5-7.0.14.dist-info" ".\dist\main.dist\yolov5-7.0.14.dist-info" /E /I /Y
xcopy ".\.venv\Lib\site-packages\yolov5\models" ".\dist\main.dist\models" /E /I /Y

:: ���������ļ��к��ļ�
xcopy ".\library" ".\dist\main.dist\library" /E /I /Y
copy ".\getNum.py" ".\dist\main.dist\getNum.py" /Y
xcopy ".\flask-dist" ".\dist\main.dist\flask-dist" /E /I /Y

cls
echo ��������
echo.
echo ׼��������...

:: ��������
.\dist\main.dist\CCRS.exe --simulate --nogui

if errorlevel 1 (
    echo ��������ʧ�ܣ����ش�����Ϣ��
) else (
    echo ������������������״̬�� 0��
)

pause