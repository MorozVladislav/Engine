# Graph Visualisation App

## Description
The application visualizes graphs described by *.json files formatted as example below:

```json
{
    "idx": 1,
    "lines": [
        {
            "idx": 192,
            "length": 1,
            "points": [
                112,
                107
            ]
        },
        {
            "idx": 193,
            "length": 2,
            "points": [
                101,
                102
            ]
        },
        ...
    ],
    "name": "map01",
    "points": [
        {
            "idx": 101,
            "post_idx": 13
        },
        {
            "idx": 102,
            "post_idx": null
        },
        ...
    ]
}
```

## Dependencies
The app requires python2.7 and pip installed. All the rest dependencies are indicated in requirements.txt

## How to run it
You can execute run.bat (for Windows) or run.sh (for Linux). In case it doesn't work for your OS you can execute next commands:
```
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```
## Developers
Moroz Vladislav: https://github.com/MorozVladislav
Vasilkova Julia: https://github.com/JuliaVasilkova
Borisov Dmitry: https://github.com/stalkerboray
