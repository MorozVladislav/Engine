# Engine

## Developers

+ Мороз Владислав - [Moroz Vladislav](https://github.com/MorozVladislav)
+ Василькова Юля - [Vasilkova Julia](https://github.com/JuliaVasilkova)
+ Борисов Дмитрий - [Borisov Dmitry](https://github.com/stalkerboray)

## Tasks

### Граф визуальный прекрасный I
[Task 1](tasks/task_1.md)

### Клиент игровой великолепный II
[Task 2](tasks/task_2.md)

## Dependencies
The application requires Python2.7 and pip installed. All the rest dependencies are indicated in requirements.txt

## How to run it
You can execute 
  - bash run.sh
  - run.bat
  - or next commands:
```
pip install -r requirements.txt
cd src
python2.7 -m main.py
```

## How to use Engine Feachers
1. Press "Play" button to start the game.
    1.1 If you have default settings in default_settings.yaml the game will start automatically
    1.2 Otherwise insert your information in "Server settings"-window fields
2. For connecting a server go to "File" -> "Server settings" fill all necessary fields and press "Ok". 
   Any server connection errors will be displayed in status bar at the top of the window."
3. For moving of any map point just grab it with left mouse button than move and drop where you want.
