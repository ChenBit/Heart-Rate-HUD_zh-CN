@echo off
if "%1"=="h" goto begin
mshta vbscript:createobject("wscript.shell").run("""%~nx0"" h",0)(window.close)&&exit
:begin
pip install -r requirements.txt
pythonw main.py
