from setuptools import setup, find_packages
import os

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="csi-base-component-sdk",
    version="2.0.2",
    author="kalinote",
    author_email="knote840746219@gmail.com",
    description="csi基本组件开发工具包",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kalinote/cyberspacein",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "csi-component=csi_base_component_sdk.runner:main",
        ]
    },
    keywords="csi component sdk async",
    project_urls={
        "Bug Reports": "https://github.com/kalinote/csi-base-component-sdk/issues",
        "Source": "https://github.com/kalinote/csi-base-component-sdk",
    },
)

