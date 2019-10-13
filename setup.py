#!/usr/bin/env python3

from sys import exit
from setuptools import setup, find_packages

# Using the version from PKGBUILD for less duplication
with open(__file__.replace("setup.py", "PKGBUILD"), mode="rt", encoding="utf-8") as fp:
	for line in fp.read().splitlines():
		if line.startswith("pkgver="):
			version = line.split("=")[1]

setup(
	name="manjaro_kernel_bundler",
	version=version,
	packages=find_packages(),
	url="https://github.com/D1SoveR/manjaro-kernel-bundler",
	author='Mikołaj "D1SoveR" Banasik',
	author_email="d1sover@gmail.com",
	description="CLI tool for bundling the Manjaro kernels, along with initramfs and kernel params for diret UEFI boot",
	entry_points={"console_scripts": [
		"manjaro-kernel-bundler = manjaro_kernel_bundler:main"
	]}
)