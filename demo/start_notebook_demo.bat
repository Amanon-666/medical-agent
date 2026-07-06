@echo off
setlocal

cd /d "%~dp0\.."

if "%CCF_TASK3_DEMO_URL%"=="" set "CCF_TASK3_DEMO_URL=https://demo.mashiro.xin/"
if "%CCF_NEXENT_CONFIG_BASE%"=="" set "CCF_NEXENT_CONFIG_BASE=https://nexent-api.mashiro.xin"
if "%CCF_NEXENT_RUNTIME_BASE%"=="" set "CCF_NEXENT_RUNTIME_BASE=https://nexent-runtime.mashiro.xin"
if "%CCF_NEXENT_EMAIL%"=="" set "CCF_NEXENT_EMAIL=suadmin@nexent.com"
if "%CCF_NEXENT_PASSWORD%"=="" set "CCF_NEXENT_PASSWORD=241002814"

echo Starting CCF Medical AI notebook demo...
jupyter notebook demo\interactive_pipeline_demo.ipynb

endlocal
