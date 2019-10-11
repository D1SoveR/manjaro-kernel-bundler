from filecmp import cmp
from os import scandir
from os.path import basename, isfile, isdir, join, splitext
from .util import run, envfile_to_params
from tempfile import NamedTemporaryFile

# Collection of classes and methods to generate database of current
# kernel bundles, for use with listing and bundling commands
# (to determine whether anything needs removal or rebundling).

class KernelBundle():

	__slots__ = ("name", "build_id", "default", "fallback", "preset")

	def __init__(self, name, build_id):
		self.name = name
		self.build_id = build_id
		self.default = False
		self.preset = None

	@property
	def path(self):
		return join(self.preset.path_root, self.preset.name, self.name) if self.preset else self.name

	@property
	def currently_used(self):
		if not self.preset:
			raise RuntimeError("Cannot determine current usage without parent preset")

		current_kernel = join(self.preset.root_path, "kernel.efi")
		return cmp(current_kernel, self.path) if isfile(current_kernel) else False

	@staticmethod
	def from_bundle(bundle_path):

		# Attempt to extract build ID from the bundle
		with NamedTemporaryFile(mode="rt", encoding="utf8") as fp:
			run(["objcopy", "--dump-section", ".osrel={0}".format(fp.name), bundle_path])
			fp.seek(0)
			params = envfile_to_params(fp.read())

		bundle = KernelBundle(basename(bundle_path), int(params["BUILD_ID"]))
		fallback_path = splitext(bundle_path)[0]
		if fallback_path:
			bundle.fallback = fallback_path if isdir(fallback_path) else None

		return bundle

class KernelPreset():

	__slots__ = ("bundles", "name", "path_root", "path_kernel", "path_initramfs")

	def __init__(self, name, bundles, path_root, path_kernel, path_initramfs):
		self.name = name
		self.bundles = bundles
		self.path_root = path_root
		self.path_kernel = path_kernel
		self.path_initramfs = path_initramfs
		for item in bundles:
			item.preset = self

	@property
	def last_build_id(self):
		return max(map(lambda x: x.build_id, self.bundles)) if len(self.bundles) else None

	@property
	def currently_used(self):
		return any(x.currently_used for x in self.bundles)

	@staticmethod
	def from_preset(name, root_path):

		# First, check if preset exists for this version
		preset_path = "/etc/mkinitcpio.d/{0}.preset".format(name)
		if not isfile(preset_path):
			raise RuntimeError("{0} is not a valid kernel preset".format(name))

		with open(preset_path, mode="rt", encoding="utf8") as fp:
			params = envfile_to_params(fp.read())
			del preset_path

		path_kernel = params["ALL_kver"]
		path_initramfs = params["default_image"]
		path_bundles = "{0}/{1}".format(root_path, name)

		if isdir(path_bundles):
			bundles = sorted((KernelBundle.from_bundle(item.path) for item in scandir(path_bundles) if item.is_file() and item.name.endswith(".efi")), key=lambda x: x.build_id)
		else:
			bundles = []

		return KernelPreset(name, bundles, root_path, path_kernel, path_initramfs)

def initialise(root_path):

	db = {}

	for item in scandir("/etc/mkinitcpio.d"):
		if item.is_file() and item.name.endswith(".preset"):

			identifier = splitext(item.name)[0]
			db[identifier] = KernelPreset.from_preset(identifier, root_path)

	return db