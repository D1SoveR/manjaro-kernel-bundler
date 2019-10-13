from filecmp import cmp
from os import scandir
from os.path import basename, isfile, isdir, join, splitext
from .util import run, envfile_to_params
from tempfile import NamedTemporaryFile

# Collection of classes and methods to generate database of current
# kernel bundles, for use with listing and bundling commands
# (to determine whether anything needs removal or rebundling).

class KernelBundle():

	"""
	Class representing single kernel bundle among all of the ones
	currently present on the system. Carries details of the bundle,
	such as its location, name, build ID, and whether it has fallback
	directory created for it as well.
	"""

	__slots__ = (
		# Used to carry the name of the kernel bundle,
		# which in current setup is kernel-[build id].efi
		"name",

		# Build ID, which is the latest of the last modified
		# timestamps of any of the bundle components: kernel
		# file itself, intramfs, AMD microcode, or command line
		# (this way modifying any of these components will cause
		#  new bundle to be generated)
		"build_id",

		# Reference to KernelPreset instance indicating which preset
		# this bundle belongs to, needed for determining location
		# of the bundle, as well as whether it's the one currently
		# used (linked at the root)
		"preset"
	)

	def __init__(self, name, build_id):

		"""
		Instantiates the bundle from given name (usually "kernel-[Build ID].efi").
		Preset is set up post-instantiation.
		"""

		self.name = name
		self.build_id = build_id
		self.preset = None

	@property
	def path_bundle(self):

		"""
		Full file path leading to this particular kernel bundle.
		"""

		if not self.preset:
			raise RuntimeError("Cannot determine path without parent preset")
		return join(self.preset.path_root, self.preset.name, self.name)

	@property
	def path_fallback(self):

		"""
		If present, path to the directory containing all the base
		components of the bundle, along with .nsh file allowing
		the user to boot from that kernel (along with all its setup)
		for debug purposes.
		If such fallback directory is not present, None.
		"""

		fallback_dir_path = splitext(self.path_bundle)[0]
		return fallback_dir_path if isdir(fallback_dir_path) else None

	@property
	def currently_used(self):

		"""
		True if this is the bundle currently linked at the root, and used for booting.
		"""

		if not self.preset:
			raise RuntimeError("Cannot determine current usage without parent preset")

		current_kernel = join(self.preset.path_root, "kernel.efi")
		return cmp(current_kernel, self.path_bundle) if isfile(current_kernel) else False

	@staticmethod
	def from_bundle(bundle_path):

		"""
		Attempts to instantiate KernelBundle object from the kernel bundle already
		present on the drive, under given location.
		"""

		if not isfile(bundle_path):
			raise ValueError("No kernel bundle under: {0}".format(bundle_path))

		# Attempt to extract build ID from the bundle
		with NamedTemporaryFile(mode="rt", encoding="utf8") as fp:
			run(["objcopy", "--dump-section", ".osrel={0}".format(fp.name), bundle_path])
			fp.seek(0)
			params = envfile_to_params(fp.read())

		return KernelBundle(basename(bundle_path), int(params["BUILD_ID"]))

class KernelPreset():

	"""
	Class representing an entire kernel preset, as defined by the Manjaro packages,
	along with .preset entries in /etc/mkinitcpio.d, such as "linux316" for 3.16 series of
	kernels, or "linux52" for 5.2 series.
	It carries all the relevant paths for its components, as well as the list of bundles
	that are part of this preset.
	"""

	__slots__ = (
		# Name representing the preset and series of kernels
		# which it represents, such as "linux316" or "linux52"
		"name",

		# List of all the bundles belonging to this specific preset
		"bundles",

		# Path pointing to the root of all the kernel bundles
		# (not just for this specific preset), used for determining
		# full paths for all the bundles, as well as locating the currently
		# used bundle (fixed-name copy at the root, due to lack of linking
		# capabilities for FAT32)
		"path_root",

		# Location of the actual kernel used for this preset, used when bundling
		"path_kernel",

		# Location of the initramfs used by this preset, used when bundling
		"path_initramfs"
	)

	def __init__(self, name, bundles, path_root, path_kernel, path_initramfs):

		"""
		Instantiates the preset with the name, all the paths, as well as
		the list of bundles that belong to it.
		"""

		self.name = name
		self.bundles = bundles
		self.path_root = path_root
		self.path_kernel = path_kernel
		self.path_initramfs = path_initramfs
		for item in bundles:
			item.preset = self

	@property
	def last_build_id(self):

		"""
		Returns the latest build ID for all the bundles handled by this preset.
		If no bundles have been made for this kernel, returns None.
		"""

		return max(map(lambda x: x.build_id, self.bundles)) if len(self.bundles) else None

	@property
	def currently_used(self):

		"""
		True if any of the bundles for this preset are used as default boot target, false otherwise.
		"""

		return any(x.currently_used for x in self.bundles)

	@staticmethod
	def from_preset(name, root_path):

		"""
		Creates the preset from the given preset name, first gathering the details and paths
		from the preset configuration file, then checking for any existing bundles.
		"""

		# First, check if preset exists for this version
		preset_path = "/etc/mkinitcpio.d/{0}.preset".format(name)
		if not isfile(preset_path):
			raise RuntimeError("{0} is not a valid kernel preset".format(name))

		# Open the preset file and extract various paths from it
		with open(preset_path, mode="rt", encoding="utf8") as fp:
			params = envfile_to_params(fp.read())
			del preset_path

		path_kernel = params["ALL_kver"]
		path_initramfs = params["default_image"]
		path_bundles = "{0}/{1}".format(root_path, name)

		# Check for any existing bundles for this preset
		if isdir(path_bundles):
			bundles = sorted((KernelBundle.from_bundle(item.path) for item in scandir(path_bundles) if item.is_file() and item.name.endswith(".efi")), key=lambda x: x.build_id)
		else:
			bundles = []

		return KernelPreset(name, bundles, root_path, path_kernel, path_initramfs)

def initialise(root_path):

	"""
	Convenience method that goes over the kernel presets available to the system,
	and instantiates KernelPresets from those, gathering them in map for further usage.
	"""

	db = {}

	for item in scandir("/etc/mkinitcpio.d"):
		if item.is_file() and item.name.endswith(".preset"):

			identifier = splitext(item.name)[0]
			db[identifier] = KernelPreset.from_preset(identifier, root_path)

	return db