from setuptools import setup, find_packages
import os

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="csi-base-component-sdk",
    version="1.0.4",
    author="kalinote",
    author_email="knote840746219@gmail.com",
    description="csi基本组件开发工具包",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kalinote/csi-base-component-sdk",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    keywords="csi component sdk async",
    project_urls={
        "Bug Reports": "https://github.com/kalinote/csi-base-component-sdk/issues",
        "Source": "https://github.com/kalinote/csi-base-component-sdk",
    },
)

