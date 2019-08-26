#!/usr/bin/env python3

import argparse
import os
import os.path
import subprocess

from db import KernelBundle
import gzip
from math import floor
from os import makedirs, remove, stat
from os.path import join
from shutil import copyfile, rmtree
from tempfile import NamedTemporaryFile
from util import run, TempFileMap

UCODE_FILE="/boot/amd-ucode.img"
CMDLINE_FILE="/boot/cmdline.txt"

def generate_bundle_for_preset(preset):

	# Very first thing, verify if bundle needs to be generated for this preset
	# (it could be that there was no change to any of the bundled files, and thus
	# the bundle does not need to be regenerated
	current_build_id = floor(max(
		stat(preset.path_kernel).st_mtime,
		stat(UCODE_FILE).st_mtime,
		stat(preset.path_initramfs).st_mtime,
		stat(CMDLINE_FILE).st_mtime
	))

	if preset.last_build_id is not None and preset.last_build_id >= current_build_id:
		print("No changes to {0} since the most recent bundle, skipping...".format(preset.name))
	else:

		bundle_name = "kernel-{0}.efi".format(current_build_id)

		print("Generating bundle for {0}...".format(preset.name))
		with TempFileMap(
			cmdline=NamedTemporaryFile(mode="w+t", encoding="utf8"),
			osrel=NamedTemporaryFile(mode="w+t", encoding="utf8"),
			initrd=NamedTemporaryFile(mode="w+b")
		) as tmpfiles:

			# Generate command-line
			with open(CMDLINE_FILE, mode="rt", encoding="utf8") as fp:
				kernel_bit = "\\\\" + preset.path_kernel.replace("/", "\\")[1:]
				tmpfiles.cmdline.write("{0} {1}".format(kernel_bit, fp.read()))
			tmpfiles.cmdline.flush()

			# Generate os-release file with added BUILD_ID parameter
			# ======================================================
			with open("/etc/os-release", mode="rt", encoding="utf8") as fp:
				tmpfiles.osrel.write(fp.read())
			print('BUILD_ID="{0}"'.format(current_build_id), file=tmpfiles.osrel)
			tmpfiles.osrel.flush()
			print("os-release file with BUILD_ID of {0} generated".format(current_build_id))

			# Generate initramfs for bundling, adding mirocode and unpacking initramfs
			# ========================================================================
			for img_file in (UCODE_FILE, preset.path_initramfs):
				file_type = run(["file", "--brief", "--mime-type", img_file])
				if file_type == "application/octet-stream":
					print("{0} is plain image, adding it to initramfs as it is...".format(img_file))
					fp = open(img_file, mode="rb")
				elif file_type == "application/gzip":
					print("{0} is gzipped, gunzipping in into initramfs".format(img_file))
					fp = gzip.open(img_file, mode="rb")
				else:
					raise Exception("Unknown initramfs type: {0}".format(file_type))

				tmpfiles.initrd.write(fp.read())
				fp.close()
			tmpfiles.initrd.flush()
			print("initramfs generated")

			# Put all of the files together into a bundle
			# ========================================================================
			
			output_dir = join(preset.path_root, preset.name)
			output_file = join(output_dir, bundle_name)
			makedirs(output_dir, exist_ok=True)

			run([
				"objcopy",
				"--add-section",   ".osrel={0}".format(tmpfiles.osrel.name),   "--change-section-vma",   ".osrel=0x20000",
				"--add-section", ".cmdline={0}".format(tmpfiles.cmdline.name), "--change-section-vma", ".cmdline=0x30000",
				"--add-section",   ".linux={0}".format(preset.path_kernel),    "--change-section-vma",   ".linux=0x2000000",
				"--add-section",  ".initrd={0}".format(tmpfiles.initrd.name),  "--change-section-vma",  ".initrd=0x3000000",
				"/usr/lib/systemd/boot/efi/linuxx64.efi.stub",
				output_file
			])
			print("kernel bundle generated at {0}\n".format(output_file))

		return KernelBundle(bundle_name, current_build_id, None)

def make_currently_used(preset):

	if len(preset.bundles):
		latest_bundle = preset.bundles[-1]
		copyfile(latest_bundle.path, join(preset.path_root, "kernel.efi"))
		print("Made {0} of {1} preset currently used kernel bundle".format(latest_bundle.name, preset.name))
	else:
		print("{0} preset has no kernel bundles, skipping...".format(preset.name))

def delete_old_bundles(preset, number_to_keep=1):

	if len(preset.bundles) > number_to_keep:

		bundles_to_delete = preset.bundles[:-number_to_keep]
		preset.bundles = preset.bundles[-number_to_keep:]

		for bundle in bundles_to_delete:
			os.remove(bundle.path)
			if bundle.fallback:
				rmtree(bundle.fallback)
		print("removed {0} outdated bundles for {1} preset".format(len(bundles_to_delete, preset.name)))
