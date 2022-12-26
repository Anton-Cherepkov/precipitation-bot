# -*- coding: utf-8 -*-
import io
from typing import List

from setuptools import find_packages, setup

with io.open("requirements.txt", "r", encoding="utf-8") as req_file:
    requires: List[str] = req_file.read().splitlines()

setup(
    name="weather_bot",
    version="0.0.1",
    description="Weather Telegram Bot",
    author="Anton Cherepkov, Nikita Yusupov",
    packages=find_packages(exclude=["tests", "tools"]),
    include_package_data=True,
    install_requires=requires,
    zip_safe=False,
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 1 - Beta",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)
