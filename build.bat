@echo off

echo ���ڳ��Թ���...
echo.

:: ������⻷���Ƿ����
if not exist ".\.venv\Scripts\python.exe" (
    echo [����] ���⻷�������ڣ����ȴ������⻷����
    pause
    exit /b
)

:: ��������
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

echo ������ɣ�
echo.
echo ���������ļ�����...
echo �벻Ҫ�رմ���
:: ���� Python �����ļ���
set SRC_DIR=.venv\Lib\site-packages
set DST_DIR=.\dist\main.dist

for %%D in (ultralytics CCRS_Library yolov5 yolov5\models torch torchaudio torchgen torchvision) do (
    if exist "%SRC_DIR%\%%D" (
        echo ���� %%D ...
        xcopy "%SRC_DIR%\%%D" "%DST_DIR%\%%D" /E /I /Y >nul
    ) else (
        echo [����] δ�ҵ� %SRC_DIR%\%%D���������ƣ�
    )
)

:: ���ƶ����ļ�
if exist ".\getNum.py" (
    copy ".\getNum.py" "%DST_DIR%\getNum.py" /Y >nul
)

if exist ".\flask-dist" (
    xcopy ".\flask-dist" "%DST_DIR%\flask-dist" /E /I /Y >nul
)

echo �������ɣ�
echo.
echo ׼������ CCRS...

:: ��������
"%DST_DIR%\CCRS.exe" --simulate

if errorlevel 1 (
    echo [����] ��������ʧ�ܣ�
) else (
    echo [�ɹ�] ��������������
)

pause
