# CineMind

An AI movie recommendation app. Modular monolith built with Python + FastAPI.

## Status

**Week 1** — project setup, MovieLens data loading, three recommenders
(collaborative filtering, content-based, hybrid), and a FastAPI surface.

## Project layout

```
cinemind/
├── app/                    # application package
│   ├── data/               # dataset download + loading
│   ├── recommenders/       # collaborative, content-based, hybrid models
│   └── main.py             # FastAPI app (added in a later step)
├── data/                   # downloaded MovieLens dataset (gitignored)
├── tests/                  # pytest suite
└── requirements.txt
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

_(Added in later steps.)_
