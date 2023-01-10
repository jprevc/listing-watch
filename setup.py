"""
Setup script
"""

from setuptools import setup

setup(
    name="news_crawlers",
    version="1.0",
    description="News crawlers",
    author="Jost Prevc",
    author_email="jost.prevc@gmail.com",
    packages=["news_crawlers"],
    install_requires=[
        "scrapy",
        "PyYAML",
        "requests",
        "numpy",
        "parameterized",
        "pytest",
    ],
)
