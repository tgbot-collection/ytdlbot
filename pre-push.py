#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - pre-commit.py
# for dependabot

import tomllib
import subprocess


with open("pyproject.toml", "rb") as file:
    config = tomllib.load(file)

with open("requirements.txt", "w") as file:
    for item in config["project"]["dependencies"]:
        if " " in item:
            item = item.split()[-1]
        file.write(f"{item}\n")

# commit with amend
subprocess.run(["git", "add", "requirements.txt"])
subprocess.run(["git", "commit", "--amend", "--no-edit"])
