#!/usr/bin/env python3

import argparse
import gzip
import math
import os
import os.path
import subprocess
import tempfile

def run(command):

	proc = subprocess.run(command, stdin=None, capture_output=True, check=True, encoding="utf8")
	return proc.stdout.strip()


def initialise_db():

	"""
	This method is used to get the information about existing kernel bundles
	from the data already residing on EFI system partition, to determine
	how many kernel/initramfs versions are kept around.
	"""

	db = {}

	for item in os.scandir("/etc/mkinitcpio.d"):
		if item.is_file() and item.name.endswith(".preset"):

			identifier = os.path.splitext(item.name)[0]
			db[identifier] = {
				"bundles": get_existing_bundles(identifier)
			}

			with open(item.path, mode="rt", encoding="utf8") as fp:
				params = filter(lambda x: len(x) == 2, map(lambda x: x.split("="), fp.read().splitlines()))
				for (key, value) in params:
					if key == "ALL_kver":
						db[identifier]["kernel"] = value[1:-1]
					elif key == "default_image":
						db[identifier]["initramfs"] = value[1:-1]

	return db

def get_existing_bundles(key):

	"""
	This method, part of initialising the DB for kernel bundles,
	takes the key (which is the name of the kernel preset), and gathers
	information about kernels for that version.
	"""

	if os.path.isdir("/boot/efi/EFI/Manjaro/{0}".format(key)):
		raise Exception("Haven't done that bit yet!")
	else:
		return []

def get_version_from_kver(key):

	version = None
	for item in os.scandir("/boot"):
		if item.is_file() and item.name.startswith(key) and item.name.endswith(".kver"):
			with open(item.path, mode="rt", encoding="utf8") as fp:
				version = fp.read().strip()
	return version

def create_bundle(key, db_entry):

	print("Generating bundle for {0}...".format(key))

	tmpfiles = {}
	tmpfiles["os_release"] = tempfile.NamedTemporaryFile(mode="w+t", encoding="utf8")
	tmpfiles["initramfs"] = tempfile.NamedTemporaryFile(mode="w+b")

	try:
		
		# Assemble os-release with extra parameters for identifying the used kernel
		with open("/etc/os-release", mode="rt", encoding="utf8") as fp:
			tmpfiles["os_release"].write(fp.read())

		kernel_version = get_version_from_kver(key)
		print('"VERSION="{0}"'.format(kernel_version), file=tmpfiles["os_release"])
		del kernel_version

		timestamp = math.floor(max(
			os.stat(db_entry["kernel"]).st_ctime,
			os.stat(db_entry["initramfs"]).st_ctime
		))
		print('BUILD_ID="{0}"'.format(timestamp), file=tmpfiles["os_release"])

		tmpfiles["os_release"].flush()
		print("os-release file with BUILD_ID of {0} created".format(timestamp))

		# Assemble bundled initramfs (optionally unpacking the images)
		print("Generating initramfs...")
		for img_file in ("/boot/amd-ucode.img", db_entry["initramfs"]):
			file_type = run(["file", "--brief", "--mime-type", img_file])

			if file_type == "application/octet-stream":
				print("{0} is plain image, adding it as it is...".format(img_file))
				fp = open(img_file, mode="rb")
			elif file_type == "application/gzip":
				print("{0} is gzipped, will gunzip it...".format(img_file))
				fp = gzip.open(img_file, mode="rb")
			else:
				raise Exception("Unknown initramfs type: {0}".format(file_type))

			tmpfiles["initramfs"].write(fp.read())
			fp.close()
			del fp
		tmpfiles["initramfs"].flush()
		print("initramfs created")

		# Put all of the files together into a bundle
		print("Generating the kernel bundle...")
		output = "/home/d1sover/kernel-{1}.efi".format(key, timestamp)
		run([
			"objcopy",
			"--add-section", ".osrel={0}".format(tmpfiles["os_release"].name), "--change-section-vma", ".osrel=0x20000",
			"--add-section", ".cmdline=/boot/cmdline.txt", "--change-section-vma", ".cmdline=0x30000",
			"--add-section", ".linux={0}".format(db_entry["kernel"]), "--change-section-vma", ".linux=0x40000",
			"--add-section", ".initrd={0}".format(tmpfiles["initramfs"].name), "--change-section-vma", ".initrd=0x3000000",
			"/usr/lib/systemd/boot/efi/linuxx64.efi.stub",
			output
		])
		print("Kernel bundle created at {0}".format(output))

	except subprocess.CalledProcessError as e:
		print("Following issue while bundling:")
		print(e)
		raise e
	finally:
		tmpfiles["os_release"].close()
		tmpfiles["initramfs"].close()

def command_list(input):
	commands = ["list", "bundle"]
	if input in commands:
		return input
	else:
		raise Exception("Command needs to be one of: {0}".format(", ".join(commands)))

if __name__ == "__main__":

	parser = argparse.ArgumentParser(description="Script to help with bundling the kernel for deployment to EFI system partition.")
	parser.add_argument("command", metavar="COMMAND", type=command_list, help="Action to take")

	args = parser.parse_args()
	db = initialise_db()

	# List all the present kernels
	if args.command == "list":

		print(db)
		exit(0)

		if len(db):
			print("Following kernels are available:")
			for (preset, kernels) in db.items():
				if len(kernels):
					pass
				else:
					print(" * {0}: No kernel bundles at a time".format(preset))
		else:
			print("No kernels avilable at a time")

	elif args.command == "bundle":

		if not os.path.isfile("/boot/cmdline.txt"):
			raise Exception("No command line file available")

		for key, db_entry in db.items():
			create_bundle(key, db_entry)