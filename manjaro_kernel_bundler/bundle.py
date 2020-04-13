#!/usr/bin/env python3

from .db import KernelBundle
import gzip
from math import floor
from os import makedirs, remove, stat
from os.path import basename, isfile, join, relpath, splitext
from shutil import copyfile, rmtree
from tempfile import NamedTemporaryFile
from .util import get_mountpoint_for, run, TempFileMap

UCODE_FILE="/boot/amd-ucode.img"
CMDLINE_FILE="/boot/cmdline.txt"

def generate_bundle_for_preset(preset, sb_dir, generate_fallback=True):

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
		return

	# If we need to generate the bundle, create its name and carry on
	bundle_name = "kernel-{0}.efi".format(current_build_id)

	print("Generating bundle for {0}...".format(preset.name))
	with TempFileMap(
		cmdline=NamedTemporaryFile(mode="w+t", encoding="utf8"),
		osrel=NamedTemporaryFile(mode="w+t", encoding="utf8"),
		initrd=NamedTemporaryFile(mode="w+b"),
		bundle=NamedTemporaryFile(mode="w+b")
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
			tmpfiles.bundle.name
		])
		print("kernel bundle generated")

		# Sign the bundle for Secure Boot
		# ========================================================================
		# Verify that the keys are available, and sign.

		output_dir = join(preset.path_root, preset.name)
		output_file = join(output_dir, bundle_name)
		makedirs(output_dir, exist_ok=True)

		if (
			isfile(join(sb_dir, "db.key")) and
			isfile(join(sb_dir, "db.crt"))
		):

			run([
				"sbsign",
				"--key",  join(sb_dir, "db.key"),
				"--cert", join(sb_dir, "db.crt"),
				"--output", output_file,
				tmpfiles.bundle.name
			])
			print("kernel bundle signed and saved at {0}\n".format(output_file))

		else:

			print("WARNING: unable to find Secure Boot key and certificate at {0}, skipping signing...".format(sb_dir))
			copyfile(tmpfiles.bundle.name, output_file)
			print("kernel bundle saved at {0}\n".format(output_file))

		if generate_fallback:
			generate_fallback_for_preset(preset, current_build_id)

	return KernelBundle(bundle_name, current_build_id)

def generate_fallback_for_preset(preset, build_id):

	output_dir = join(preset.path_root, preset.name, "kernel-{0}".format(build_id))
	makedirs(output_dir)

	# Copy the kernel (requires addition of .efi extension to be properly recognised
	# when being run from EFI shell), along with the initramfs and microcode
	dest_kernel = join(output_dir, "{0}.efi".format(basename(preset.path_kernel)))
	dest_initramfs = join(output_dir, basename(preset.path_initramfs))
	dest_ucode = join(output_dir, basename(UCODE_FILE))
	copyfile(preset.path_kernel, dest_kernel)
	copyfile(preset.path_initramfs, dest_initramfs)
	copyfile(UCODE_FILE, dest_ucode)

	# Generate the launch.nsh EFI script that launches the kernel with all its command line
	# intact, and loading the right initramfs and ucode. This requires converting some paths,
	# not just for backslashes, but also to be relative to EFI partition mountpoint.
	esp_mountpoint = get_mountpoint_for(preset.path_root)

	def convert_path(path):
		return "\\" + relpath(path, esp_mountpoint).replace("/", "\\")

	# Create launch.nsh file, containing the command to execute the copied kernel, along with
	# loading the initramfs, microcode, and executing all the commands listed in the command file
	with open(CMDLINE_FILE, mode="rt", encoding="utf-8") as fp:
		commands = fp.read().strip()
	with open(join(output_dir, "launch.nsh"), mode="wt", encoding="utf-8") as fp:
		print("{0} initrd={1} initrd={2} {3}".format(
			convert_path(dest_kernel),
			convert_path(dest_ucode),
			convert_path(dest_initramfs),
			commands
		), file=fp)

	print("Generated fallback for build ID of {0}".format(build_id))

def make_currently_used(preset):

	if len(preset.bundles):
		latest_bundle = preset.bundles[-1]
		copyfile(latest_bundle.path_bundle, join(preset.path_root, "kernel.efi"))
		print("Made {0} of {1} preset currently used kernel bundle".format(latest_bundle.name, preset.name))
	else:
		print("{0} preset has no kernel bundles, skipping...".format(preset.name))

def delete_old_bundles(preset, number_to_keep=1):

	if len(preset.bundles) > number_to_keep:

		bundles_to_delete = preset.bundles[:-number_to_keep]
		preset.bundles = preset.bundles[-number_to_keep:]

		for bundle in bundles_to_delete:
			remove(bundle.path_bundle)
			if bundle.path_fallback:
				rmtree(bundle.path_fallback)
		print("removed {0} outdated bundles for {1} preset".format(len(bundles_to_delete), preset.name))
