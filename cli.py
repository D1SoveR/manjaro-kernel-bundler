#!/usr/bin/env python3

import argparse
from db import initialise

def command_list(input):
	if input != "list" and input != "update":
		raise RuntimeError("Command needs to be one of: list, update")
	return input

if __name__ == "__main__":

	parser = argparse.ArgumentParser(description="Script helping with managing kernel bundles on EFI system partition.")
	parser.add_argument("--root", metavar="DIRECTORY", action="store", default="/boot/efi/EFI/Manjaro", required=False, help="Which directory should be used as base for all the kernel bundles")
	parser.add_argument("command", metavar="list|bundle", action="store", type=command_list, help="Whether to list existingf bundles, or attempt to create new ones")

	params = parser.parse_args()
	db = initialise(params.root)

	if params.command == "list":

		if len(db):
			print("Following kernels are available:")
			for preset in db.values():
				if len(preset.bundles):
					print(" * Following bundles exist for {0}:".format(preset.preset))
					for bundle in preset.bundles:
						print("   - {0}".format(bundle.name))
				else:
					print(" * {0}: No kernel bundles at a time".format(preset.preset))
		else:
			print("No kernel bundles available at a time")

	elif params.command == "bundle":

		raise RuntimeError("Not yet")