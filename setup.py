from setuptools import setup, find_packages

setup(
    name="lukhed_sports",
    version="0.9.1",
    description="A collection of sports analysis utility functions and API wrappers",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="lukhed",
    author_email="lukhed.mail@gmail.com",
    url="https://github.com/lukhed/lukhed_sports",
    packages=find_packages(),
    include_package_data=True,  # Ensures MANIFEST.in is used
    python_requires=">=3.9",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "lukhed-basic-utils>=1.5.0",
        "nameparser>=1.1.3",
        "fuzzywuzzy>=0.18.0",
        "Levenshtein>=0.27.1"
    ],
)