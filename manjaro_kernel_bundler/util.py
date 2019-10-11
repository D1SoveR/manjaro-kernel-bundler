# This file contains various helpers used throughout the kernel bundling code.

import subprocess

def run(commands):

	"""
	Basic helper for executing external programs within context of the bundling script.
	It is primarily used for executing objcopy (for bundling/extracting) and file (for determining whether initramfs is compressed).
	Takes an array of strings which will assemble command to execute, same as subprocess.run(), and will return the output of the command.
	"""

	proc = subprocess.run(commands, stdin=None, capture_output=True, check=True, encoding="utf8")
	return proc.stdout.strip()

def envfile_to_params(data):

	"""
	Converts environment file content into a dictionary with all the parameters.
	If your input looks like:

	# comment
	NUMBER=123
	KEY="value"

	Then the generated dictionary will be the following:

	{
		"NUMBER": "123",
		"KEY": "value"
	}
	"""

	params = filter(lambda x: len(x) == 2, map(lambda x: x.split("="), data.splitlines()))
	return { k: v[1:-1] if v.startswith('"') and v.endswith('"') else v for (k, v) in params }

class TempFileMap():

	"""
	Helper for managing multiple temporary files with help of context "with" syntax:

	with TempFileMap(
		foo=NamedTemporaryFile(mode="w+t", encoding="utf-8"),
		bar=TemporaryFile(mode="w+b")
	) as tmpfiles:

		foo.write("spam")
		bar.write(b"ham")

		print(foo.flush() and foo.seek(0) and foo.read()) # prints "spam"

	print("All of the temporary files are correctly closed now")
	"""

	__slots__ = ("_tmpfiles")

	def __init__(self, **kwargs):
		self._tmpfiles = kwargs

	def __enter__(self):
		return self

	def __exit__(self, x, y, z):
		for file in self._tmpfiles.values():
			file.close()

	def __getattr__(self, name):
		if name in self._tmpfiles:
			return self._tmpfiles[name]
		else:
			raise AttributeError("{0} is not an available temporary file".format(name))
