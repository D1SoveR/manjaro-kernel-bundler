from os import scandir
from os.path import basename, isfile, isdir, splitext
from util import run, envfile_to_params
from tempfile import NamedTemporaryFile

# Collection of classes and methods to generate database of current
# kernel bundles, for use with listing and bundling commands
# (to determine whether anything needs removal or rebundling).

class KernelBundle():

	__slots__ = ("name", "build_id", "default", "fallback")

	def __init__(self, name, build_id, fallback):
		self.name = name
		self.build_id = build_id
		self.fallback = fallback
		self.default = False

	@staticmethod
	def from_bundle(bundle_path):

		# Attempt to extract build ID from the bundle
		with NamedTemporaryFile(mode="rt", encoding="utf8") as fp:
			run(["objcopy", "--dump-section", ".osrel={0}".format(fp.name), bundle_path])
			fp.seek(0)
			params = envfile_to_params(fp.read())

		fallback_path = splitext(bundle_path)[0]

		return KernelBundle(
			basename(bundle_path),
			int(params["BUILD_ID"]),
			fallback_path if isdir(fallback_path) else None
		)

class KernelPreset():

	__slots__ = ("bundles", "preset", "path_root", "path_kernel", "path_initramfs")

	def __init__(self, preset, bundles, path_root, path_kernel, path_initramfs):
		self.preset = preset
		self.bundles = bundles
		self.path_root = path_root
		self.path_kernel = path_kernel
		self.path_initramfs = path_initramfs

	@property
	def recent_build_id(self):
		return max(map(lambda x: x.build_id, self.bundles)) if len(self.bundles) else None

	@staticmethod
	def from_preset(preset, root_path):

		# First, check if preset exists for this version
		preset_path = "/etc/mkinitcpio.d/{0}.preset".format(preset)
		if not isfile(preset_path):
			raise RuntimeError("{0} is not a valid kernel preset".format(preset))

		with open(preset_path, mode="rt", encoding="utf8") as fp:
			params = envfile_to_params(fp.read)
			del preset_path

		path_kernel = params["ALL_kver"]
		path_initramfs = params["default_image"]
		bundles = list(KernelBundle.from_bundle(item.path) for item in scandir("{0}/{1}".format(root_path, preset)) if item.is_file() and item.name.endswith(".efi"))

		return KernelPreset(preset, bundles, root_path, path_kernel, path_initramfs)

def initialise_db(root_path):

	db = {}

	for item in os.scandir("/etc/mkinitcpio.d"):
		if item.is_file() and item.name.endswith(".preset"):

			identifier = splitext(item.name)[0]
			db[identifier] = KernelPreset.from_preset(identifier, root_path)

	return db