#!/usr/bin/env python3

from sys import exit
from setuptools import setup, find_packages

setup(
	name="manjaro_kernel_bundler",
	version="0.0.1",
	packages=find_packages(),
	url="https://github.com/D1SoveR/manjaro-kernel-bundler",
	author='Mikołaj "D1SoveR" Banasik',
	author_email="d1sover@gmail.com",
	description="CLI tool for bundling the Manjaro kernels, along with initramfs and kernel params for diret UEFI boot",
	entry_points={"console_scripts": [
		"manjaro-kernel-bundler = manjaro_kernel_bundler:main"
	]}
)