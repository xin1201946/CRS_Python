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
".\.venv\Scripts\python.exe" -m nuitka --standalone --follow-imports --output-dir=.\dist --enable-plugin=no-qt --include-module=ultralytics  --include-module=CCRS_Library --include-module=tensorflow --module-parameter=torch-disable-jit=no --windows-icon-from-ico=.\CCRS.ico --windows-product-name="CCRS" --windows-file-description="Casting Char Recognition System" --product-version=2.0.5 --file-version=2.0.5 --output-filename=CCRS main.py 

echo �������
echo.
echo �������Ĳ���...
echo �벻Ҫ�رմ���

:: ���Ʊ�Ҫ���ļ��к��ļ�
xcopy ".\.venv\Lib\site-packages\ultralytics" ".\dist\main.dist\ultralytics" /E /I /Y
xcopy ".\.venv\Lib\site-packages\CCRS_Library" ".\dist\main.dist\CCRS_Library" /E /I /Y
xcopy ".\.venv\Lib\site-packages\yolov5" ".\dist\main.dist\yolov5" /E /I /Y
xcopy ".\.venv\Lib\site-packages\yolov5\models" ".\dist\main.dist\models" /E /I /Y
:: ���������޲�
xcopy ".\.venv\Lib\site-packages\torch" ".\dist\main.dist\torch" /E /I /Y
xcopy ".\.venv\Lib\site-packages\torchaudio" ".\dist\main.dist\torchaudio" /E /I /Y
xcopy ".\.venv\Lib\site-packages\torchgen" ".\dist\main.dist\torchgen" /E /I /Y
xcopy ".\.venv\Lib\site-packages\torchvision" ".\dist\main.dist\torchvision" /E /I /Y

copy ".\getNum.py" ".\dist\main.dist\getNum.py" /Y
xcopy ".\flask-dist" ".\dist\main.dist\flask-dist" /E /I /Y


echo ��������
echo.
echo ׼��������...

:: ��������
.\dist\main.dist\CCRS.exe --simulate

if errorlevel 1 (
    echo ��������ʧ�ܣ����ش�����Ϣ��
) else (
    echo ������������������״̬�� 0��
)

pause