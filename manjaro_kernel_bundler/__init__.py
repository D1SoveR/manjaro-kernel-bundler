#!/usr/bin/env python3

import argparse
from .bundle import generate_bundle_for_preset, make_currently_used, delete_old_bundles
from .db import initialise

def command_list(input):
	if input != "list" and input != "bundle":
		raise RuntimeError("Command needs to be one of: list, bundle")
	return input

def main():

	parser = argparse.ArgumentParser(description="Script helping with managing kernel bundles on EFI system partition.")
	parser.add_argument("--root", metavar="DIRECTORY", action="store", default="/boot/efi/EFI/Manjaro", required=False, help="Which directory should be used as base for all the kernel bundles")
	parser.add_argument("command", metavar="list|bundle", action="store", type=command_list, help="Whether to list existing bundles, or attempt to create new ones")

	params = parser.parse_args()
	db = initialise(params.root)

	if params.command == "list":

		if len(db):
			print("Following kernels are available:")
			for preset in db.values():
				if len(preset.bundles):
					print(" * Following bundles exist for {0}:".format(preset.name))
					for bundle in preset.bundles:
						print("   - {0}{1}".format(bundle.name, " (currently used)" if bundle.currently_used else ""))
				else:
					print(" * {0}: No kernel bundles at a time".format(preset.name))
		else:
			print("No kernel bundles available at a time")

	elif params.command == "bundle":

		for preset in db.values():
			new_bundle = generate_bundle_for_preset(preset, True)
			if new_bundle:
				new_bundle.preset = preset
				preset.bundles.append(new_bundle)
				if preset.currently_used:
					make_currently_used(preset)
				delete_old_bundles(preset, 3)

if __name__ == "__main__":
	main()