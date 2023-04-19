[PyCharm2020.1] stores PyCharm personal IDE settings

==== Linux ====

mkdir ~/.config/JetBrains/
cp -r  PyCharm2020.1/  ~/.config/JetBrains/

==== Windows ==== (CE is Community Edition)
mkdir %AppData%\JetBrains
xcopy /y /i /s  PyCharm2020.1  %AppData%\JetBrains\PyCharmCE2023.1
