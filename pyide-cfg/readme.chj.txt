[PyCharm2020.1] stores  PyCharm personal IDE settings

mkdir ~/.config/JetBrains/
cp -r  PyCharm2020.1/  ~/.config/JetBrains/

== OR ==

mkdir ~/.config/JetBrains/
ln -s ~/gitw/pyutils/pyide-cfg/PyCharm2020.1/  ~/.config/JetBrains/PyCharm2020.1 

== OR == (on Windows) (CE is Community Edition)
mkdir %AppData%\JetBrains
xcopy /y /i /s PyCharm2020.1 %AppData%\JetBrains\PyCharmCE2020.2
