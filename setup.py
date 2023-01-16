#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from setuptools import setup
import warnings

with open("README.md", "r") as fh:
    long_description = fh.read()

try:
    from numpy.distutils.core import Extension
    from numpy.distutils.core import setup
except ImportError:
    print('Error: numpy needs to be installed first')
    sys.exit(1)

import pathlib

PACKAGENAME = 'eddy'

extensions = Extension(name=f'{PACKAGENAME}._fortran', sources=[f'{PACKAGENAME}/fortran.f90'])

# the directory where this setup.py resides

HERE = pathlib.Path(__file__).absolute().parent

# function to parse the version from

if __name__ == "__main__":
    def run_setup(extensions):
        setup(
            name="astro-eddy",
            version="2.2",
            author="Richard Teague",
            author_email="rteague@mit.edu",
            description=("Tools to recover expectionally precise rotation curves from "
                        "spatially resolved spectra."),
            long_description=long_description,
            long_description_content_type="text/markdown",
            url="https://github.com/richteague/eddy",
            license="MIT",
            packages=["eddy"],
            package_data= {PACKAGENAME: [
                'eddy/fortran.f90',
            ]},
            include_package_data=True,
            ext_modules=[extensions],
            install_requires=[
                "scipy>=1",
                "numpy",
                "matplotlib>=3",
                "emcee>=3",
                "corner>=2",
                "zeus-mcmc",
                ],
            package_data={'eddy': ['*.yml']},
            include_package_data=True,
            classifiers=[
                "Programming Language :: Python :: 3.5",
                "License :: OSI Approved :: MIT License",
                "Operating System :: OS Independent",
            ],
        )
    try:
        run_setup(extensions)
    except Exception:
        warnings.warn('Setup with extensions did not work. Install fortran manually by issuing `make` in the diskwarp sub-folder')
        run_setup([])