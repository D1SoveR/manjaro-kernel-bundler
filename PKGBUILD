# Maintainer: Mikołaj Banasik <d1sover@gmail.com>

# Base package info
pkgname="manjaro-kernel-bundler"
pkgver=0.0.2
pkgrel=1
pkgdesc="CLI tool for bundling the Manjaro kernels, along with initramfs and kernel params for direct UEFI boot"
url="https://github.com/D1SoveR/manjaro-kernel-bundler"

# Dependencies
arch=("any")
license=("custom:Public Domain")
depends=("python")
provides=("$pkgname")
conflicts=("$pkgname")

# Package contents
source=("git+git${url#https}.git#tag=v${pkgver}")
md5sums=("SKIP")

pkgver() {
	cd "${srcdir}/${pkgname}"
	local version="$(git describe --tags)"
	echo ${version#v}
}

package() {

	cd "${srcdir}/${pkgname}"

	# Install the actual package
	python setup.py install --prefix=/usr --root="$pkgdir" --optimize=1

	# Install the hook allowing regeneration on every installation
	install -Dm644 "${srcdir}/${pkgname}/kernel-bundler.hook" "${pkgdir}/usr/share/libalpm/hooks/99-kernel-bundler.hook"

	# Install the UNLICENSE because Manjaro has no pre-defined license for Public Domain
	install -D -m644 "${srcdir}/${pkgname}/LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"

}